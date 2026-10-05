# -*- coding: utf-8 -*-
# ==============================================================================
# PARTE 1 DE 3: Importações, Inicialização, Estado e Aba de Lançamentos
# ==============================================================================
import os
import sys
import re
import threading
import io
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP, getcontext
import tkinter as tk
from tkinter import simpledialog, ttk, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mtick

# Importações de módulos locais
import database as db
import calculos
import exportacao
import importacao_pdf
from utilidades import (
    _dec, money_pt, fmt_moeda, fmt_kg, clean_str, tag_por_estado, 
    to_float_safe, format_data_ptbr_abbrev, normalizar, get_df_com_peso_real
)
from componentes import ModernMessageBox, CalendarioPremium, obter_data_segura
from telas_secundarias import abrir_gestao_feriados

class SistemaGestaoAmbiental:
    def __init__(self, root):
        self.root = root
        self.root.title("Gerenciamento de Resíduos")
        self.root.geometry("1200x820")
        self.root.minsize(1040, 720)
        self.root.state('zoomed')

        # ==========================================
        # 1. ESTADO DA APLICAÇÃO (Sem Globais)
        # ==========================================
        self.editing_id = None
        self.df_registros = pd.DataFrame()
        self.df_banco = pd.DataFrame()
        self.banco_dict = {}
        self.df_parceiros = pd.DataFrame()
        self.parceiros = []
        self.lista_destinadores = []
        self.lista_transportadores = []
        self.lista_laboratorios = []
        self.lista_todos_parceiros = []
        self.df_analises = pd.DataFrame()
        self.lista_analises = []
        self.analises_dict = {}
        self.banco_residuos = []
        self.banco_residuos_rateio = []
        self.destinacoes = []
        self.destinacoes_unicas = []
        self.DATA_CORTE_ISO = '2023-01-01'
        self.DEFAULT_DESTINACOES = [
            "Reciclagem", "Blendagem para coprocessamento", "Compostagem",
            "Incineração", "Tratamento de efluentes", "N/A", "Logística reversa"
        ]

        # Validadores de entrada
        self.vcmd_numeric = (self.root.register(self.validate_numeric), '%P')

        # ==========================================
        # 2. INICIALIZAÇÃO SEGURA DO BANCO
        # ==========================================
        db.initialize_database()
        db.criar_tabela_feriados()

        # ==========================================
        # 3. ESTILOS E ÍCONES
        # ==========================================
        self.style = tb.Style()
        self.style.configure('.', font=('Segoe UI', 9))
        self.style.configure("Treeview", rowheight=28)
        self.style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'))
        self.carregar_icones()

        # ==========================================
        # 4. CONSTRUÇÃO DA INTERFACE VISUAL
        # ==========================================
        self.construir_interface()
        self.config_tags_por_tema()

        # ==========================================
        # 5. CARREGAMENTO INICIAL DE DADOS
        # ==========================================
        self.atualizar_views()
        self.clear_form()
        self.clear_form_analise()
        
        # Ligações e eventos finais do app
        self.root.protocol("WM_DELETE_WINDOW", self.realizar_backup_e_fechar)

    def validate_numeric(self, P):
        return P == "" or bool(re.match(r"^[0-9]*[,]?[0-9]*$", P))

    def carregar_icones(self):
        self.icons = {}
        icon_files = {
            "add": "icon_add.png", "edit": "icon_edit.png",
            "delete": "icon_delete.png", "ok": "icon_ok.png",
            "duplicate": "icon_duplicate.png"
        }
        try:
            base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
            for key, filename in icon_files.items():
                path = os.path.join(base_path, filename)
                if os.path.exists(path):
                    self.icons[key] = tk.PhotoImage(file=path)
                else:
                    self.icons[key] = None
        except:
            pass

    def get_resource_path(self, relative_path):
        try: base_path = sys._MEIPASS
        except Exception: base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # ==============================================================================
    # ESTRUTURAÇÃO DA UI MODULAR
    # ==============================================================================
    def construir_interface(self):
        # Cabeçalho
        self.header = tb.Frame(self.root, padding=(12,10))
        self.header.pack(fill="x")
        
        # Logo
        try:
            from PIL import Image, ImageTk
            arquivo_logo = self.get_resource_path("logo.png")
            if os.path.exists(arquivo_logo):
                pil_image = Image.open(arquivo_logo)
                proporcao = 45 / float(pil_image.size[1])
                largura_nova = int(float(pil_image.size[0]) * proporcao)
                pil_image = pil_image.resize((largura_nova, 45), Image.Resampling.LANCZOS)
                self.tk_logo = ImageTk.PhotoImage(pil_image)
                lbl_logo = tb.Label(self.header, image=self.tk_logo)
                lbl_logo.pack(side="left", padx=(0, 15))
        except: pass

        tb.Label(self.header, text="CONTROLE DE DESTINAÇÃO DE RESÍDUOS E ANÁLISES EXTERNAS", font="-size 16 -weight bold").pack(side="left")

        self.status_var = tk.StringVar(value="")
        tb.Label(self.header, textvariable=self.status_var, bootstyle=SECONDARY).pack(side="right", padx=8)
        self.tema_btn = tb.Button(self.header, text="Alternar tema", bootstyle=SECONDARY, cursor="hand2", command=self.alternar_tema)
        self.tema_btn.pack(side="right")

        # Rodapé ISO
        self.footer_frame = tb.Frame(self.root, padding=2, bootstyle="secondary")
        self.footer_frame.pack(side="bottom", fill="x")
        self.footer_frame.columnconfigure((0, 1, 2), weight=1)
        tb.Label(self.footer_frame, text="Código do Documento: FO-5.1.00.016", font=("Segoe UI", 8), anchor="center", bootstyle="inverse-secondary").grid(row=0, column=0, sticky="ew", padx=(0, 1))
        tb.Label(self.footer_frame, text="Aprovado em: 26/06/2024", font=("Segoe UI", 8), anchor="center", bootstyle="inverse-secondary").grid(row=0, column=1, sticky="ew", padx=1)
        tb.Label(self.footer_frame, text="Revisão: 08", font=("Segoe UI", 8), anchor="center", bootstyle="inverse-secondary").grid(row=0, column=2, sticky="ew", padx=(1, 0))

        # Notebook Principal
        self.nb = tb.Notebook(self.root, bootstyle=PRIMARY)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0,12))

        # Sub-montagens
        self.setup_aba_cadastro()
        self.setup_aba_calendario()
        self.setup_aba_registros()
        self.setup_aba_pendencias()
        self.setup_aba_relatorios()
        self.setup_aba_configuracoes()

    # ==============================================================================
    # ABA 1: LANÇAMENTOS (CADASTRO)
    # ==============================================================================
    def setup_aba_cadastro(self):
        self.aba_cad_fundo = tb.Frame(self.nb)
        self.nb.add(self.aba_cad_fundo, text="Resíduos")
        self.aba_cad_fundo.columnconfigure(0, weight=1); self.aba_cad_fundo.columnconfigure(1, weight=0); self.aba_cad_fundo.columnconfigure(2, weight=1)
        self.aba_cad = tb.Frame(self.aba_cad_fundo, padding=12)
        self.aba_cad.grid(row=0, column=1, sticky="n", pady=10)
        tb.Frame(self.aba_cad, width=1000, height=1).pack()

        # Tipo Lançamento
        self.launch_type_var = tk.StringVar(value="Resíduo")
        self.launch_frame = tb.Labelframe(self.aba_cad, text="Tipo de Lançamento", padding=(10, 5), bootstyle=INFO)
        self.launch_frame.pack(fill="x", pady=(0, 10))
        tb.Radiobutton(self.launch_frame, text="Resíduo", value="Resíduo", variable=self.launch_type_var).pack(side="left", padx=10)
        tb.Radiobutton(self.launch_frame, text="Transporte", value="Transporte", variable=self.launch_type_var).pack(side="left", padx=10)
        tb.Radiobutton(self.launch_frame, text="Análise Externa", value="Análise", variable=self.launch_type_var).pack(side="left", padx=10)

        # ----------------------------------------------------
        # FORM 1: RESÍDUO
        # ----------------------------------------------------
        self.cad = tb.Labelframe(self.aba_cad, text="Novo registro", padding=12, bootstyle=INFO)
        self.cad.columnconfigure((0,1,2,3), weight=1, uniform="group1")

        tb.Label(self.cad, text="Data").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.entrada_data = CalendarioPremium(self.cad, dateformat="%d/%m/%y")
        self.entrada_data.grid(row=1, column=0, sticky="ew", padx=(0,5), pady=(2, 12))

        tb.Label(self.cad, text="Resíduo").grid(row=0, column=1, sticky="w", padx=5)
        self.res_var = tk.StringVar()
        self.res_cb = tb.Combobox(self.cad, textvariable=self.res_var, state="normal")
        self.res_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(2, 12))

        tb.Label(self.cad, text="Parceiro").grid(row=0, column=2, sticky="w", padx=5)
        self.parceiro_var = tk.StringVar()
        self.parceiro_cb = tb.Combobox(self.cad, textvariable=self.parceiro_var, state="normal")
        self.parceiro_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(2, 12))

        tb.Label(self.cad, text="Tipo").grid(row=0, column=3, sticky="w", padx=(5,0))
        self.tipo_var = tk.StringVar(value="Venda")
        self.tipo_frame = tb.Frame(self.cad)
        self.tipo_frame.grid(row=1, column=3, sticky="w", padx=(5,0), pady=(2, 12))
        tb.Radiobutton(self.tipo_frame, text="Venda", value="Venda", variable=self.tipo_var).pack(side="left", padx=(2,12))
        tb.Radiobutton(self.tipo_frame, text="Custo", value="Custo", variable=self.tipo_var).pack(side="left")

        tb.Label(self.cad, text="Estado").grid(row=2, column=0, sticky="w", padx=(0,5))
        self.estado_var = tk.StringVar(value="Sólido")
        self.estado_frame = tb.Frame(self.cad)
        self.estado_frame.grid(row=3, column=0, sticky="w", padx=(0,5), pady=(0, 10))
        tb.Radiobutton(self.estado_frame, text="Sólido", value="Sólido", variable=self.estado_var).pack(side="left", padx=(0,10))
        tb.Radiobutton(self.estado_frame, text="Líquido", value="Líquido", variable=self.estado_var).pack(side="left")

        tb.Label(self.cad, text="Destinação").grid(row=2, column=1, sticky="w", padx=5)
        self.destinacao_var = tk.StringVar()
        self.destinacao_cb = tb.Combobox(self.cad, textvariable=self.destinacao_var, state="readonly")
        self.destinacao_cb.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 10))

        tb.Label(self.cad, text="Pedido de compra (opcional)").grid(row=2, column=2, sticky="w", padx=5)
        self.entrada_pedido = tb.Entry(self.cad)
        self.entrada_pedido.grid(row=3, column=2, sticky="ew", padx=5, pady=(0, 10))

        self.frame_compliance = tb.Frame(self.cad)
        self.frame_compliance.grid(row=3, column=3, sticky="w", padx=5, pady=(0,10))
        self.caminho_anexo_temp = tk.StringVar(value="")
        self.btn_anexo = tb.Button(self.frame_compliance, text="Anexar", bootstyle="outline-secondary", command=self.selecionar_anexo, width=8)
        self.btn_anexo.pack(side="left", padx=(15, 5))
        self.lbl_anexo_info = tb.Label(self.frame_compliance, text="", font=("Segoe UI", 8))
        self.lbl_anexo_info.pack(side="left")

        self.var_nf_manual = tk.IntVar(value=1)
        self.var_cert_manual = tk.IntVar(value=1)
        tb.Checkbutton(self.frame_compliance, text="Exige NF", variable=self.var_nf_manual, bootstyle="round-toggle").pack(side="left", padx=(0, 10))
        tb.Checkbutton(self.frame_compliance, text="Exige Certificado", variable=self.var_cert_manual, bootstyle="round-toggle").pack(side="left")

        # Cálculos Resíduo
        self.calc_lf = tb.Labelframe(self.cad, text="Cálculo de Valores", padding=15, bootstyle=INFO)
        self.calc_lf.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(15, 5))
        self.calc_lf.columnconfigure((0, 1, 2, 3), weight=1, uniform="group2") 

        self.calc_mode_var = tk.StringVar(value="kg")
        self.radio_frame = tb.Frame(self.calc_lf)
        self.radio_frame.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,15))
        tb.Radiobutton(self.radio_frame, text="Valor por kg", value="kg", variable=self.calc_mode_var).pack(side="left", padx=(0,20))
        tb.Radiobutton(self.radio_frame, text="Valor por unidade", value="unidade", variable=self.calc_mode_var).pack(side="left", padx=(0,20))
        tb.Radiobutton(self.radio_frame, text="Valor fechado", value="fechado", variable=self.calc_mode_var).pack(side="left", padx=0)

        # -- Col 0: Valores --
        self.label_valor_kg = tb.Label(self.calc_lf, text="Valor por kg (R$)")
        self.label_valor_kg.grid(row=1, column=0, sticky="w")
        self.entrada_valor_kg = tb.Entry(self.calc_lf, validate="key", validatecommand=self.vcmd_numeric)
        self.entrada_valor_kg.grid(row=2, column=0, sticky="ew", padx=(0,10), pady=(0, 15))

        self.label_valor_fechado = tb.Label(self.calc_lf, text="Valor fechado (R$)")
        self.label_valor_fechado.grid(row=1, column=0, sticky="w")
        self.entrada_valor_fechado = tb.Entry(self.calc_lf, validate="key", validatecommand=self.vcmd_numeric)
        self.entrada_valor_fechado.grid(row=2, column=0, sticky="ew", padx=(0,10), pady=(0, 15))

        # -- Col 1: Peso --
        self.peso_var = tk.StringVar()
        self.label_peso = tb.Label(self.calc_lf, text="Peso (kg)", bootstyle=INFO)
        self.label_peso.grid(row=1, column=1, sticky="w")
        self.entrada_peso = tb.Entry(self.calc_lf, textvariable=self.peso_var, validate="key", validatecommand=self.vcmd_numeric)
        self.entrada_peso.grid(row=2, column=1, sticky="ew", padx=(0,10), pady=(0, 15))
        
        # -- Col 2: Peso Unitario --
        self.peso_unitario_var = tk.StringVar()
        self.label_peso_unitario = tb.Label(self.calc_lf, text="Peso por Unidade (kg)")
        self.label_peso_unitario.grid(row=1, column=2, sticky="w")
        self.entrada_peso_unitario = tb.Entry(self.calc_lf, textvariable=self.peso_unitario_var, validate="key", validatecommand=self.vcmd_numeric)
        self.entrada_peso_unitario.grid(row=2, column=2, sticky="ew", padx=(0,10), pady=(0, 15))
        
        # -- Col 3: Peso Total Calculado --
        self.peso_kg_var = tk.StringVar()
        self.label_peso_kg = tb.Label(self.calc_lf, text="Peso Total (kg)", bootstyle=SUCCESS)
        self.label_peso_kg.grid(row=1, column=3, sticky="w")
        self.entrada_peso_kg = tb.Entry(self.calc_lf, textvariable=self.peso_kg_var, state="readonly", bootstyle="success")
        self.entrada_peso_kg.grid(row=2, column=3, sticky="ew", padx=(0,0), pady=(0, 15))

        # Transporte e Separador
        tb.Separator(self.calc_lf).grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        tb.Label(self.calc_lf, text="Transporte (R$) [Custo Extra]").grid(row=4, column=0, sticky="w")
        self.entrada_transporte = tb.Entry(self.calc_lf, validate="key", validatecommand=self.vcmd_numeric)
        self.entrada_transporte.grid(row=5, column=0, sticky="ew", padx=(0,10))

        self.frame_total_destaque = tb.Frame(self.calc_lf)
        self.frame_total_destaque.grid(row=4, column=2, rowspan=2, columnspan=2, sticky="e")
        tb.Label(self.frame_total_destaque, text="TOTAL DA OPERAÇÃO", font=("Segoe UI", 9, "bold")).pack(side="top", anchor="e")
        self.lbl_total_operacao = tb.Label(self.frame_total_destaque, text="R$ 0,00", font=("Segoe UI", 24, "bold"), bootstyle="success")
        self.lbl_total_operacao.pack(side="top", anchor="e")

        self.cad_actions = tb.Frame(self.aba_cad)
        self.btn_submit = tb.Button(self.cad_actions, text="Adicionar Registro", bootstyle=SUCCESS, width=20, command=self.submit_registro_event)
        self.btn_submit.pack(side="left", padx=(0, 15))
        self.btn_clear_form = tb.Button(self.cad_actions, text="Limpar Formulário", bootstyle="secondary-outline", width=20, command=self.clear_form)
        self.btn_clear_form.pack(side="left")
        self.btn_lote = tb.Button(self.cad_actions, text="Lançamento em Lote (Carga)", bootstyle="info-outline", command=self.abrir_janela_lote)
        self.btn_lote.pack(side="right", padx=10)

        # ----------------------------------------------------
        # FORM 2: ANÁLISE EXTERNA
        # ----------------------------------------------------
        self.frm_ana = tb.Labelframe(self.aba_cad, text="Nova análise externa", padding=12, bootstyle=INFO)
        for i in range(3): self.frm_ana.columnconfigure(i, weight=1)
        tb.Label(self.frm_ana, text="Data").grid(row=0, column=0, sticky="w", padx=(0,8))
        self.ana_data = CalendarioPremium(self.frm_ana, dateformat="%d/%b/%y")
        self.ana_data.grid(row=1, column=0, sticky="ew", padx=(0,8), pady=(0, 10))
        tb.Label(self.frm_ana, text="Laboratório / Parceiro").grid(row=0, column=1, sticky="w", padx=(0,8))
        self.ana_parc_var = tk.StringVar()
        self.ana_parc_cb = tb.Combobox(self.frm_ana, textvariable=self.ana_parc_var, state="readonly")
        self.ana_parc_cb.grid(row=1, column=1, sticky="ew", padx=(0,8), pady=(0, 10))
        tb.Label(self.frm_ana, text="Nome da análise").grid(row=0, column=2, sticky="w", padx=(0,0))
        self.ana_nome_var = tk.StringVar()
        self.ana_nome_cb = tb.Combobox(self.frm_ana, textvariable=self.ana_nome_var, state="readonly")
        self.ana_nome_cb.grid(row=1, column=2, sticky="ew", padx=(0,0), pady=(0, 10))
        tb.Label(self.frm_ana, text="Valor fechado (R$)").grid(row=2, column=0, sticky="w", padx=(0,8), pady=(10,0))
        self.ana_valor_fechado = tb.Entry(self.frm_ana, validate="key", validatecommand=self.vcmd_numeric)
        self.ana_valor_fechado.grid(row=3, column=0, sticky="ew", padx=(0,8))
        
        self.frame_compl_ana = tb.Frame(self.frm_ana)
        self.frame_compl_ana.grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=5)
        self.var_nf_ana = tk.IntVar(value=1)
        self.var_cert_ana = tk.IntVar(value=0)
        tb.Checkbutton(self.frame_compl_ana, text="Exige NF", variable=self.var_nf_ana, bootstyle="round-toggle").pack(side="left", padx=(0, 15))
        tb.Checkbutton(self.frame_compl_ana, text="Exige Certificado", variable=self.var_cert_ana, bootstyle="round-toggle").pack(side="left")

        tb.Label(self.frm_ana, text="Pedido de compra (opcional)").grid(row=2, column=1, sticky="w", padx=(0,8), pady=(10,0))
        self.ana_pedido = tb.Entry(self.frm_ana)
        self.ana_pedido.grid(row=3, column=1, sticky="ew", padx=(0,8))
        self.btn_ana_add = tb.Button(self.aba_cad, text="Adicionar análise (custo)", bootstyle=SUCCESS, command=self.adicionar_analise_event)

        # ----------------------------------------------------
        # FORM 3: TRANSPORTE
        # ----------------------------------------------------
        self.frm_transporte = tb.Labelframe(self.aba_cad, text="Novo Lançamento de Frete", padding=12, bootstyle=WARNING)
        self.frm_transporte.columnconfigure((0, 1, 2), weight=1)
        tb.Label(self.frm_transporte, text="Data").grid(row=0, column=0, sticky="w", padx=5)
        self.transp_data = CalendarioPremium(self.frm_transporte, dateformat="%d/%b/%y")
        self.transp_data.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))
        tb.Label(self.frm_transporte, text="Transportadora").grid(row=0, column=1, sticky="w", padx=5)
        self.transp_parc_var = tk.StringVar()
        self.transp_parc_cb = tb.Combobox(self.frm_transporte, textvariable=self.transp_parc_var, state="readonly")
        self.transp_parc_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 10))
        tb.Label(self.frm_transporte, text="Resíduo Atrelado (Obrigatório)").grid(row=0, column=2, sticky="w", padx=5)
        self.transp_res_var = tk.StringVar()
        self.transp_res_cb = tb.Combobox(self.frm_transporte, textvariable=self.transp_res_var, state="readonly")
        self.transp_res_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 10))
        tb.Label(self.frm_transporte, text="Valor do Frete (R$)").grid(row=2, column=0, sticky="w", padx=5)
        self.transp_valor = tb.Entry(self.frm_transporte, validate="key", validatecommand=self.vcmd_numeric)
        self.transp_valor.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 10))
        tb.Label(self.frm_transporte, text="Pedido de Compra / Ticket").grid(row=2, column=1, columnspan=2, sticky="w", padx=5)
        self.transp_pedido = tb.Entry(self.frm_transporte)
        self.transp_pedido.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=(0, 10))
        
        self.frame_compl_transp = tb.Frame(self.frm_transporte)
        self.frame_compl_transp.grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        self.var_nf_transp = tk.IntVar(value=1)
        self.var_cert_transp = tk.IntVar(value=0)
        tb.Checkbutton(self.frame_compl_transp, text="Exige NF (CT-e)", variable=self.var_nf_transp, bootstyle="round-toggle").pack(side="left", padx=(0, 15))
        tb.Checkbutton(self.frame_compl_transp, text="Exige Certificado", variable=self.var_cert_transp, bootstyle="round-toggle").pack(side="left")
        
        self.btn_transporte_add = tb.Button(self.frm_transporte, text="Adicionar Frete (Custo)", bootstyle=WARNING, command=self.adicionar_transporte_event)
        self.btn_transporte_add.grid(row=5, column=0, columnspan=3, sticky="w", padx=5, pady=10)

        # Configuração de Binds Iniciais (Aba 1)
        self.res_var.trace_add("write", self.atualizar_form_por_residuo)
        self.res_cb.bind("<<ComboboxSelected>>", self.atualizar_form_por_residuo)
        self.res_cb.bind("<Return>", lambda e: self.atualizar_form_por_residuo())
        self.res_cb.bind("<FocusOut>", lambda e: self.atualizar_form_por_residuo())
        
        self.calc_mode_var.trace_add("write", lambda *_: self.toggle_campos_por_modo())
        self.tipo_var.trace_add("write", lambda *_: self.toggle_pedido_por_tipo())
        self.peso_var.trace_add("write", self.calcular_peso_kg_automatico)
        self.peso_unitario_var.trace_add("write", self.calcular_peso_kg_automatico)
        self.calc_mode_var.trace_add("write", self.calcular_peso_kg_automatico)
        
        self.entrada_valor_kg.bind("<KeyRelease>", self.calcular_resumo_financeiro_automatico)
        self.entrada_valor_fechado.bind("<KeyRelease>", self.calcular_resumo_financeiro_automatico)
        self.entrada_transporte.bind("<KeyRelease>", self.calcular_resumo_financeiro_automatico)
        
        self.launch_type_var.trace_add("write", self.toggle_launch_view)
        self.launch_type_var.trace_add("write", self.atualizar_combobox_parceiro_dinamico)
        self.ana_nome_var.trace_add("write", self.atualizar_valor_por_analise)
        self.ana_nome_cb.bind("<<ComboboxSelected>>", self.atualizar_valor_por_analise)

    # ==============================================================================
    # Construção das Abas de Calendário, Registros, Relatórios e Config
    # ==============================================================================

    def setup_aba_calendario(self):
        self.aba_cal = tb.Frame(self.nb, padding=10)
        self.nb.add(self.aba_cal, text="Calendário")
        self.aba_cal.columnconfigure(0, weight=3); self.aba_cal.columnconfigure(1, weight=1)
        self.aba_cal.rowconfigure(0, weight=1)

        # Lado Esquerdo: Calendário
        self.frame_cal_widget = tb.Labelframe(self.aba_cal, text="Visão Mensal", padding=10, bootstyle=INFO)
        self.frame_cal_widget.grid(row=0, column=0, sticky="nsew", padx=(0,10))

        self.frame_nav_cal = tb.Frame(self.frame_cal_widget)
        self.frame_nav_cal.pack(fill="x", pady=(0, 10))

        self.titulo_mes_var = tk.StringVar(value="Mês Atual")
        tb.Button(self.frame_nav_cal, text="< Anterior", bootstyle="outline-primary", command=lambda: self.navegar_calendario(-1)).pack(side="left")
        self.lbl_mes_cal = tb.Label(self.frame_nav_cal, textvariable=self.titulo_mes_var, font=("Segoe UI", 14, "bold"), bootstyle="primary", anchor="center")
        self.lbl_mes_cal.pack(side="left", fill="x", expand=True)
        tb.Button(self.frame_nav_cal, text="Hoje", bootstyle="info-outline", command=self.ir_para_hoje).pack(side="left", padx=10)
        tb.Button(self.frame_nav_cal, text="Próximo >", bootstyle="outline-primary", command=lambda: self.navegar_calendario(1)).pack(side="left")

        from tkcalendar import Calendar
        self.cal_visual = Calendar(self.frame_cal_widget, selectmode='day', date_pattern='dd/mm/yyyy', cursor="hand2", showweeknumbers=False, showothermonthdays=False, firstweekday='sunday')
        self.cal_visual.pack(fill="both", expand=True, pady=5)
        self.cal_visual.bind("<<CalendarSelected>>", self.on_cal_click)
        self.cal_visual.bind("<<CalendarMonthChanged>>", self.atualizar_titulo_mes)

        tb.Label(self.frame_cal_widget, text="Legenda: 🟢 = Dia com Movimentação Registrada", bootstyle="success").pack(pady=5)

        # Lado Direito: Detalhes
        self.frame_cal_detalhes = tb.Labelframe(self.aba_cal, text="Detalhes do Dia Selecionado", padding=10, bootstyle=WARNING)
        self.frame_cal_detalhes.grid(row=0, column=1, sticky="nsew", padx=(5,0))

        cal_cols = ("Resíduo", "Parceiro", "Peso/Qtd", "Valor Total", "Tipo")
        self.cal_tree = ttk.Treeview(self.frame_cal_detalhes, columns=cal_cols, show="headings", selectmode="extended")
        self.cal_tree.heading("Resíduo", text="Resíduo"); self.cal_tree.column("Resíduo", width=130, anchor="center")
        self.cal_tree.heading("Parceiro", text="Parceiro"); self.cal_tree.column("Parceiro", width=100, anchor="center")
        self.cal_tree.heading("Peso/Qtd", text="Peso / Qtd"); self.cal_tree.column("Peso/Qtd", width=140, anchor="center")
        self.cal_tree.heading("Valor Total", text="Total (R$)"); self.cal_tree.column("Valor Total", width=90, anchor="center")
        self.cal_tree.heading("Tipo", text="Tipo"); self.cal_tree.column("Tipo", width=60, anchor="center")
        self.cal_tree.pack(fill="both", expand=True)
        self.cal_tree.bind("<<TreeviewSelect>>", self.somar_selecao_calendario)

        self.lbl_soma_cal = tb.Label(self.frame_cal_detalhes, text="Total Selecionado: R$ 0,00", font=("Segoe UI", 11, "bold"), bootstyle="inverse-info", anchor="center")
        self.lbl_soma_cal.pack(fill="x", pady=(5,0))

    def setup_aba_registros(self):
        self.aba_regs = tb.Frame(self.nb, padding=12)
        self.nb.add(self.aba_regs, text="Registros")
        
        self.filtros = tb.Labelframe(self.aba_regs, text="Filtros", padding=(10, 5), bootstyle=INFO)
        self.filtros.pack(fill="x", pady=(0, 10))
        for i in range(5): self.filtros.columnconfigure(i, weight=1, uniform="filters")

        # Filtros Dropdown
        tb.Label(self.filtros, text="Parceiro").grid(row=0, column=0, sticky="w", padx=(0,5), pady=(0,2))
        self.f_parc = tk.StringVar(value="Todos")
        self.parc_menu = tb.Combobox(self.filtros, textvariable=self.f_parc, values=["Todos"], state="readonly")
        self.parc_menu.grid(row=1, column=0, sticky="ew", padx=(0,10), pady=(0, 10))

        tb.Label(self.filtros, text="Resíduo").grid(row=0, column=1, sticky="w", padx=(0,5), pady=(0,2))
        self.f_res = tk.StringVar(value="Todos")
        self.res_menu = tb.Combobox(self.filtros, textvariable=self.f_res, values=["Todos"], state="readonly")
        self.res_menu.grid(row=1, column=1, sticky="ew", padx=(0,10), pady=(0, 10))

        tb.Label(self.filtros, text="Estado").grid(row=0, column=2, sticky="w", padx=(0,5), pady=(0,2))
        self.f_estado = tk.StringVar(value="Todas")
        tb.Combobox(self.filtros, textvariable=self.f_estado, values=["Todas", "Sólido", "Líquido"], state="readonly").grid(row=1, column=2, sticky="ew", padx=(0,10), pady=(0, 10))

        tb.Label(self.filtros, text="Destinação").grid(row=0, column=3, sticky="w", padx=(0,5), pady=(0,2))
        self.f_dest = tk.StringVar(value="Todas")
        self.dest_menu = tb.Combobox(self.filtros, textvariable=self.f_dest, values=["Todas"], state="readonly")
        self.dest_menu.grid(row=1, column=3, sticky="ew", padx=(0,10), pady=(0, 10))

        tb.Label(self.filtros, text="Tipo").grid(row=0, column=4, sticky="w", padx=(0,5), pady=(0,2))
        self.f_tipo = tk.StringVar(value="Todos")
        tb.Combobox(self.filtros, textvariable=self.f_tipo, values=["Todos", "Venda", "Custo"], state="readonly").grid(row=1, column=4, sticky="ew", padx=(0,10), pady=(0, 10))

        # Filtros de Datas e Busca
        self.frame_datas = tb.Frame(self.filtros)
        self.frame_datas.grid(row=3, column=0, columnspan=2, sticky="w", padx=0, pady=(0,10))
        tb.Label(self.filtros, text="Data Início").grid(row=2, column=0, sticky="w", padx=(0,5), pady=(0,2))
        self.f_data_inicio = CalendarioPremium(self.frame_datas, dateformat="%d/%m/%y")
        self.f_data_inicio.set_date(datetime.now().date().replace(day=1))
        self.f_data_inicio.pack(side="left", padx=(0, 5))
        
        tb.Label(self.filtros, text="Data Fim").grid(row=2, column=1, sticky="w", padx=(0,5), pady=(0,2))
        self.f_data_fim = CalendarioPremium(self.frame_datas, dateformat="%d/%m/%y")
        self.f_data_fim.set_date(datetime.now().date())
        self.f_data_fim.pack(side="left", padx=(0, 10))

        tb.Button(self.frame_datas, text="Este Mês", bootstyle="outline-primary", width=8, command=lambda: self.aplicar_filtro_rapido("mes")).pack(side="left", padx=2)
        tb.Button(self.frame_datas, text="Mês Passado", bootstyle="outline-primary", width=12, command=lambda: self.aplicar_filtro_rapido("mes_passado")).pack(side="left", padx=2)
        tb.Button(self.frame_datas, text="Este Ano", bootstyle="outline-primary", width=8, command=lambda: self.aplicar_filtro_rapido("ano")).pack(side="left", padx=2)
        tb.Button(self.frame_datas, text="Tudo", bootstyle="outline-secondary", width=6, command=lambda: self.aplicar_filtro_rapido("tudo")).pack(side="left", padx=2)

        tb.Label(self.filtros, text="Busca (Parceiro/Pedido)").grid(row=2, column=2, columnspan=2, sticky="w", padx=(0,5), pady=(0,2))
        self.f_busca = tk.StringVar()
        tb.Entry(self.filtros, textvariable=self.f_busca).grid(row=3, column=2, columnspan=2, sticky="ew", padx=(0,10), pady=(0, 10))

        self.btn_limpar_filtros = tb.Button(self.filtros, text="Limpar Filtros", bootstyle="secondary-outline", command=self.limpar_filtros_ui)
        self.btn_limpar_filtros.grid(row=3, column=3, sticky="e", padx=(0, 5), pady=(0, 10))
        self.btn_filtrar_regs = tb.Button(self.filtros, text="Filtrar", bootstyle=SUCCESS, command=self.atualizar_views)
        self.btn_filtrar_regs.grid(row=3, column=4, sticky="e", padx=(0, 10), pady=(0, 10))

        # Binds dos filtros
        self.f_parc.trace_add("write", lambda *_: self.atualizar_views())
        self.f_res.trace_add("write", lambda *_: self.atualizar_views())
        self.f_estado.trace_add("write", lambda *_: self.atualizar_views())
        self.f_dest.trace_add("write", lambda *_: self.atualizar_views())
        self.f_busca.trace_add("write", lambda *_: self.atualizar_views())
        self.f_tipo.trace_add("write", lambda *_: self.atualizar_views())

        # Tabela
        self.tbl_card = tb.Labelframe(self.aba_regs, text="Registros", padding=6, bootstyle=INFO)
        self.tbl_card.pack(fill="both", expand=True, pady=(10,0))
        self.tbl_card.rowconfigure(0, weight=1); self.tbl_card.columnconfigure(0, weight=1)

        self.colunas_tv = ["Data","Parceiro","Resíduo","Estado","Destinação","Tipo", "Peso","Valor por kg/unidade","Valor fechado", "Valor Total", "Transporte", "Pedido de Compra", "Certificado OK", "NF OK"]
        self.tabela = ttk.Treeview(self.tbl_card, columns=self.colunas_tv, show="headings", selectmode="extended")
        self.tabela.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(self.tbl_card, orient="vertical", command=self.tabela.yview)
        sx = ttk.Scrollbar(self.tbl_card, orient="horizontal", command=self.tabela.xview)
        self.tabela.configure(yscroll=sy.set, xscroll=sx.set)
        sy.grid(row=0, column=1, sticky="ns"); sx.grid(row=1, column=0, sticky="ew")

        larg = {"Data": 85, "Parceiro": 160, "Resíduo": 160, "Estado": 70, "Destinação": 140, "Tipo": 70, "Peso": 100, "Valor por kg": 100, "Valor fechado": 100, "Transporte": 100, "Valor Total": 110, "Pedido de Compra": 110, "Certificado OK": 70, "NF OK": 60}
        cols_numericas = ["Peso", "Valor por kg", "Valor fechado", "Transporte", "Valor Total"]
        cols_centro = ["Data", "Parceiro", "Resíduo", "Estado", "Destinação", "Tipo", "Certificado OK", "NF OK"]

        for c in self.colunas_tv:
            header_name = "R$/kg" if c == "Valor por kg/unidade" else c
            meu_anchor = "e" if c in cols_numericas else "center"
            self.tabela.heading(c, text=header_name, command=lambda col=c: self.ordenar_coluna(col, False))
            self.tabela.column(c, width=larg.get(c, 100), anchor=meu_anchor, stretch=True)

        self.tabela.bind("<<TreeviewSelect>>", self.atualizar_resumo_selecao)
        self.tabela.bind("<Delete>", lambda e: self.excluir_registros_selecionados())
        self.menu_tabela = tk.Menu(self.root, tearoff=0)
        self.menu_tabela.add_command(label="Ver Anexo/Comprovante", command=self.abrir_anexo_selecionado)
        self.menu_tabela.add_separator()
        self.menu_tabela.add_command(label="Editar Registro", command=self.iniciar_edicao)
        self.tabela.bind("<Button-3>", self.mostrar_menu_tabela)

        # Botões de Ação da Tabela
        self.act_area = tb.Frame(self.aba_regs)
        self.act_area.pack(fill="x", pady=(5, 10))
        self.act_buttons_left = tb.Frame(self.act_area)
        self.act_buttons_left.pack(side="left", fill="x", expand=True)

        self.btn_edit = tb.Button(self.act_buttons_left, text="Editar", image=self.icons.get("edit"), compound=LEFT, bootstyle=INFO, command=self.iniciar_edicao)
        self.btn_duplicar = tb.Button(self.act_buttons_left, text="Duplicar", image=self.icons.get("duplicate"), compound=LEFT, command=self.duplicar_registro)
        self.btn_del = tb.Button(self.act_buttons_left, text="Excluir", image=self.icons.get("delete"), compound=LEFT, bootstyle=DANGER, command=self.excluir_registros_selecionados)
        self.btn_cert = tb.Button(self.act_buttons_left, text="Certificado OK", image=self.icons.get("ok"), compound=LEFT, bootstyle=SUCCESS, command=self.marcar_certificados_ok)
        self.btn_nf = tb.Button(self.act_buttons_left, text="NF OK", image=self.icons.get("ok"), compound=LEFT, bootstyle="success-outline", command=self.marcar_nf_ok)
        self.btn_exigencias = tb.Button(self.act_buttons_left, text="Edição em lote", image=self.icons.get("edit"), compound=LEFT, bootstyle="warning", command=self.alterar_exigencias_lote)

        self.btn_edit.pack(side="left", padx=(0, 8)); self.btn_duplicar.pack(side="left", padx=8); self.btn_del.pack(side="left", padx=8)
        self.btn_cert.pack(side="left", padx=8); self.btn_nf.pack(side="left", padx=8); self.btn_exigencias.pack(side="left", padx=8)

        self.resumo_selecao_var = tk.StringVar(value="")
        self.lbl_resumo_selecao = tb.Label(self.act_buttons_left, textvariable=self.resumo_selecao_var, bootstyle=SECONDARY, anchor="w")
        self.lbl_resumo_selecao.pack(side="left", fill="x", expand=True, padx=10, pady=(5, 0))

        self.btn_exportar_regs = tb.Button(self.act_area, text="📊 Exportar Tabela (Excel)", bootstyle="success", command=self.exportar_para_excel)
        self.btn_exportar_regs.pack(side="right", anchor="se", padx=(10, 0), pady=(5,0))
        self.btn_gerar_nf = tb.Button(self.act_area, text="Gerar Solicitação NF", bootstyle="outline-success", command=self.gerar_solicitacao_nf)
        self.btn_gerar_nf.pack(side="right", anchor="se", padx=(10, 0), pady=(5,0))

    def setup_aba_pendencias(self):
        self.aba_pend = tb.Frame(self.nb, padding=12)
        self.nb.add(self.aba_pend, text="Pendências")
        
        pend_card = tb.Labelframe(self.aba_pend, text="Certificados Pendentes (mais de 30 dias)", padding=6, bootstyle=WARNING)
        pend_card.pack(fill="both", expand=True, pady=(0,0)); pend_card.rowconfigure(0, weight=1); pend_card.columnconfigure(0, weight=1)
        
        self.pend_cols = ("Data", "Parceiro", "Resíduo")
        self.pend_tbl = ttk.Treeview(pend_card, columns=self.pend_cols, show="headings", selectmode="browse")
        self.pend_tbl.grid(row=0, column=0, sticky="nsew")
        pend_sy = ttk.Scrollbar(pend_card, orient="vertical", command=self.pend_tbl.yview)
        self.pend_tbl.configure(yscroll=pend_sy.set); pend_sy.grid(row=0, column=1, sticky="ns")
        
        pend_larg = {"Data": 110, "Parceiro": 250, "Resíduo": 250}
        for c in self.pend_cols:
            self.pend_tbl.heading(c, text=c, anchor="center")
            self.pend_tbl.column(c, width=pend_larg.get(c, 120), anchor="center", stretch=True)
            
        self.pend_tbl.bind("<Double-1>", self.marcar_pendencia_ok)

    def setup_aba_relatorios(self):
        self.aba_relatorios = tb.Frame(self.nb, padding=12)
        self.nb.add(self.aba_relatorios, text="Relatórios")
        self.relatorios_nb = tb.Notebook(self.aba_relatorios, bootstyle=PRIMARY)
        self.relatorios_nb.pack(fill="both", expand=True)

        # -------------------- DASHBOARD HOME --------------------
        self.aba_dash = tb.Frame(self.relatorios_nb, padding=25)
        self.relatorios_nb.add(self.aba_dash, text=" 🏠 Resumo do Mês ")
        tb.Label(self.aba_dash, text="Desempenho Ambiental (Mês Atual)", font=("Segoe UI", 22, "bold"), bootstyle="primary").pack(pady=(0, 30))
        frame_cards = tb.Frame(self.aba_dash); frame_cards.pack(fill="x", expand=True); frame_cards.columnconfigure((0, 1, 2), weight=1)
        
        card_peso = tb.Labelframe(frame_cards, text=" Total Gerado (kg) ", bootstyle="info", padding=20)
        card_peso.grid(row=0, column=0, sticky="nsew", padx=10)
        self.lbl_dash_peso = tb.Label(card_peso, text="0,00 kg", font=("Segoe UI", 32, "bold"), bootstyle="info")
        self.lbl_dash_peso.pack(expand=True, pady=15)

        card_custo = tb.Labelframe(frame_cards, text=" Custo Total (R$) ", bootstyle="danger", padding=20)
        card_custo.grid(row=0, column=1, sticky="nsew", padx=10)
        self.lbl_dash_custo = tb.Label(card_custo, text="R$ 0,00", font=("Segoe UI", 32, "bold"), bootstyle="danger")
        self.lbl_dash_custo.pack(expand=True, pady=15)

        card_rec = tb.Labelframe(frame_cards, text=" Taxa de Circularidade ", bootstyle="success", padding=20)
        card_rec.grid(row=0, column=2, sticky="nsew", padx=10)
        self.lbl_dash_rec = tb.Label(card_rec, text="0,0%", font=("Segoe UI", 32, "bold"), bootstyle="success")
        self.lbl_dash_rec.pack(expand=True, pady=15)

        # -------------------- ANÁLISE --------------------
        self.aba_ana = tb.Frame(self.relatorios_nb, padding=15)
        self.relatorios_nb.add(self.aba_ana, text="Análise")
        ana_filtros_frame = tb.Frame(self.aba_ana); ana_filtros_frame.pack(fill="x", pady=(0, 15))
        tb.Label(ana_filtros_frame, text="Período:", font=("Segoe UI", 10, "bold"), bootstyle="primary").pack(side="left", padx=(0, 10))
        self.ana_data_inicio = CalendarioPremium(ana_filtros_frame, dateformat="%d/%m/%Y"); self.ana_data_inicio.set_date(date(2025, 1, 1)); self.ana_data_inicio.pack(side="left", padx=5)
        tb.Label(ana_filtros_frame, text="até").pack(side="left", padx=5)
        self.ana_data_fim = CalendarioPremium(ana_filtros_frame, dateformat="%d/%m/%Y"); self.ana_data_fim.set_date(datetime.now().date()); self.ana_data_fim.pack(side="left", padx=5)
        
        tb.Label(ana_filtros_frame, text="|", bootstyle="secondary").pack(side="left", padx=10)
        tb.Button(ana_filtros_frame, text="Este Mês", bootstyle="outline-primary", width=9, command=lambda: self.aplicar_filtro_rapido_ana("mes")).pack(side="left", padx=2)
        tb.Button(ana_filtros_frame, text="Mês Passado", bootstyle="outline-primary", width=12, command=lambda: self.aplicar_filtro_rapido_ana("mes_passado")).pack(side="left", padx=2)
        tb.Button(ana_filtros_frame, text="Este Ano", bootstyle="outline-primary", width=9, command=lambda: self.aplicar_filtro_rapido_ana("ano")).pack(side="left", padx=2)
        tb.Button(ana_filtros_frame, text="Tudo", bootstyle="outline-secondary", width=6, command=lambda: self.aplicar_filtro_rapido_ana("tudo")).pack(side="left", padx=2)
        self.btn_atualizar_ana = tb.Button(ana_filtros_frame, text="Atualizar", bootstyle=SUCCESS, cursor="hand2", command=self.atualizar_dashboard)
        self.btn_atualizar_ana.pack(side="right", padx=0)

        # KPIs Análise
        kpi_frame = tb.Frame(self.aba_ana); kpi_frame.pack(fill="x", pady=(0, 15)); kpi_frame.columnconfigure((0,1,2,3), weight=1, uniform="kpi")
        self.kpi_vendas_var = tk.StringVar(value="R$ 0,00"); self.kpi_custos_var = tk.StringVar(value="R$ 0,00"); self.kpi_lucro_var = tk.StringVar(value="R$ 0,00"); self.kpi_peso_var = tk.StringVar(value="0 kg")
        def criar_card_kpi(parent, titulo, var_valor, cor_bootstyle, col_idx):
            card = tb.Frame(parent, bootstyle=f"{cor_bootstyle}", relief="raised", borderwidth=1); card.grid(row=0, column=col_idx, sticky="ew", padx=5 if col_idx > 0 else 0)
            tb.Label(card, text=titulo.upper(), font=("Segoe UI", 8), bootstyle=f"{cor_bootstyle}-inverse").pack(fill="x", pady=(5,0), padx=10)
            tb.Label(card, textvariable=var_valor, font=("Segoe UI", 16, "bold"), bootstyle=f"{cor_bootstyle}-inverse").pack(fill="x", pady=(0,10), padx=10)
        criar_card_kpi(kpi_frame, "Total Vendas", self.kpi_vendas_var, "success", 0)
        criar_card_kpi(kpi_frame, "Total Custos", self.kpi_custos_var, "danger", 1)
        criar_card_kpi(kpi_frame, "Lucro Líquido", self.kpi_lucro_var, "primary", 2)
        criar_card_kpi(kpi_frame, "Peso Total", self.kpi_peso_var, "info", 3)
        self.tot_txt = tk.Text(self.aba_ana, height=1) # Usado pelo cálculos (escondido)

        # Gráficos Análise (Instancia as figuras no self)
        graficos_frame = tb.Frame(self.aba_ana); graficos_frame.pack(fill="both", expand=True, pady=(0, 15)); graficos_frame.columnconfigure(0, weight=1, uniform="graf"); graficos_frame.columnconfigure(1, weight=1, uniform="graf")
        frame_barras = tb.Frame(graficos_frame, relief="solid", borderwidth=1); frame_barras.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tb.Label(frame_barras, text=" Comparativo Financeiro", font=("Segoe UI", 10, "bold"), bootstyle="secondary").pack(fill="x", pady=5, padx=5)
        self.fig_bar, self.ax_bar = plt.subplots(figsize=(5, 3)); self.fig_bar.tight_layout(pad=2)
        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=frame_barras); self.canvas_bar.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        dash_notebook = tb.Notebook(graficos_frame, bootstyle="light"); dash_notebook.grid(row=0, column=1, sticky="nsew")
        tab_pie_custo = tb.Frame(dash_notebook, padding=5); dash_notebook.add(tab_pie_custo, text="Custos")
        self.fig_pie_custo, self.ax_pie_custo = plt.subplots(figsize=(4, 3)); self.fig_pie_custo.tight_layout(pad=1); self.canvas_pie_custo = FigureCanvasTkAgg(self.fig_pie_custo, master=tab_pie_custo); self.canvas_pie_custo.get_tk_widget().pack(fill="both", expand=True)
        tab_pie_peso = tb.Frame(dash_notebook, padding=5); dash_notebook.add(tab_pie_peso, text="Volumes")
        self.fig_pie_peso, self.ax_pie_peso = plt.subplots(figsize=(4, 3)); self.fig_pie_peso.tight_layout(pad=1); self.canvas_pie_peso = FigureCanvasTkAgg(self.fig_pie_peso, master=tab_pie_peso); self.canvas_pie_peso.get_tk_widget().pack(fill="both", expand=True)
        tab_lucro_res = tb.Frame(dash_notebook, padding=5); dash_notebook.add(tab_lucro_res, text="Lucro/Resíduo")
        self.fig_lucro_res, self.ax_lucro_res = plt.subplots(figsize=(4, 3)); self.fig_lucro_res.tight_layout(pad=1); self.canvas_lucro_res = FigureCanvasTkAgg(self.fig_lucro_res, master=tab_lucro_res); self.canvas_lucro_res.get_tk_widget().pack(fill="both", expand=True)
        tab_evol = tb.Frame(dash_notebook, padding=5); dash_notebook.add(tab_evol, text="Evolução (13 Meses)")
        self.fig_evol, self.ax_evol = plt.subplots(figsize=(4, 3)); self.fig_evol.tight_layout(pad=1); self.canvas_evol = FigureCanvasTkAgg(self.fig_evol, master=tab_evol); self.canvas_evol.get_tk_widget().pack(fill="both", expand=True)
        tab_estado_fin = tb.Frame(dash_notebook, padding=5); dash_notebook.add(tab_estado_fin, text="Financeiro por categoria")
        self.fig_estado_fin, self.ax_estado_fin = plt.subplots(figsize=(4, 3)); self.fig_estado_fin.tight_layout(pad=1); self.canvas_estado_fin = FigureCanvasTkAgg(self.fig_estado_fin, master=tab_estado_fin); self.canvas_estado_fin.get_tk_widget().pack(fill="both", expand=True)

        # Tabela Resumo da Análise
        table_container = tb.Frame(self.aba_ana); table_container.pack(fill="both", expand=True)
        header_tbl = tb.Frame(table_container); header_tbl.pack(fill="x", pady=(0, 5))
        tb.Label(header_tbl, text="Detalhamento Mensal", font=("Segoe UI", 10, "bold"), bootstyle="secondary").pack(side="left")
        self.btn_export_dash = tb.Button(header_tbl, text="Exportar Excel", bootstyle="success-outline", cursor="hand2", command=self.exportar_dados_dashboard); self.btn_export_dash.pack(side="right")
        self.btn_pdf = tb.Button(header_tbl, text="Relatório PDF", bootstyle="danger-outline", cursor="hand2", command=self.exportar_dashboard_pdf); self.btn_pdf.pack(side="right", padx=0)
        self.btn_sinir = tb.Button(header_tbl, text="Exportar p/ SINIR", bootstyle="info", cursor="hand2", command=self.exportar_para_sinir); self.btn_sinir.pack(side="right", padx=(0, 10))

        self.resumo_cols = ("Mês","Estado","Destinacao","Peso","Vendas","Custos","Transporte","Lucro")
        self.resumo_tbl = ttk.Treeview(table_container, columns=self.resumo_cols, show="headings", height=5)
        resumo_larg = {"Mês": 80, "Estado": 80, "Destinacao": 150, "Peso": 100, "Vendas": 100, "Custos": 100, "Transporte": 100, "Lucro": 100}
        for col in self.resumo_cols:
            self.resumo_tbl.heading(col, text="Destinação" if col == "Destinacao" else col)
            self.resumo_tbl.column(col, width=resumo_larg.get(col, 100), anchor='center')
        self.resumo_tbl.pack(side="left", fill="both", expand=True)
        r_sy = ttk.Scrollbar(table_container, orient="vertical", command=self.resumo_tbl.yview); self.resumo_tbl.configure(yscroll=r_sy.set); r_sy.pack(side="right", fill="y")
        self.resumo_tbl.bind("<Double-1>", self.mostrar_detalhes_resumo)

        # -------------------- ESG E OUTROS DASHBOARDS --------------------
        # (Para não alongar excessivamente, as instâncias de Matplotlib das outras sub-abas 
        #  ESG, Balança, Geração e Ecoeficiência seguem a mesma lógica e estão garantidas na arquitetura.)
        
        self.setup_aba_esg()
        self.setup_aba_balanca()
        self.setup_aba_geracao()
        self.setup_aba_ecoeficiencia()

    def setup_aba_esg(self):
        self.aba_esg = tb.Frame(self.relatorios_nb, padding=12)
        self.relatorios_nb.add(self.aba_esg, text="Indicadores ESG")
        esg_filtros_frame = tb.Labelframe(self.aba_esg, text="Filtros ESG", padding=10, bootstyle=INFO); esg_filtros_frame.pack(fill="x", pady=(0, 10)); esg_filtros_frame.columnconfigure((0, 1, 2, 3), weight=1)
        tb.Label(esg_filtros_frame, text="Data Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
        self.esg_data_inicio = CalendarioPremium(esg_filtros_frame, dateformat="%d/%m/%Y"); self.esg_data_inicio.set_date(date(2025, 1, 1)); self.esg_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))
        tb.Label(esg_filtros_frame, text="Data Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
        self.esg_data_fim = CalendarioPremium(esg_filtros_frame, dateformat="%d/%m/%Y"); self.esg_data_fim.set_date(datetime.now().date()); self.esg_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))
        self.btn_gerar_esg = tb.Button(esg_filtros_frame, text="Gerar Relatório ESG", bootstyle=SUCCESS, command=self.start_esg_calculation); self.btn_gerar_esg.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10,0))
        
        esg_cards_frame = tb.Frame(self.aba_esg); esg_cards_frame.pack(fill="x", pady=(15, 10), padx=10)
        card_esg_geracao = tb.Labelframe(esg_cards_frame, text=" Geração Total no Período (kg) ", bootstyle="info", padding=15); card_esg_geracao.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.lbl_esg_geracao = tb.Label(card_esg_geracao, text="0,00 kg", font=("Segoe UI", 24, "bold"), bootstyle="info"); self.lbl_esg_geracao.pack()
        card_esg_taxa = tb.Labelframe(esg_cards_frame, text=" Taxa de Circularidade (%) ", bootstyle="success", padding=15); card_esg_taxa.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.lbl_esg_taxa = tb.Label(card_esg_taxa, text="0,0%", font=("Segoe UI", 24, "bold"), bootstyle="success"); self.lbl_esg_taxa.pack()
        
        esg_graf_frame = tb.Labelframe(self.aba_esg, text=" Distribuição por Destinação Final ", bootstyle="warning", padding=10); esg_graf_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.fig_esg_rosca, self.ax_esg_rosca = plt.subplots(figsize=(6, 4)); self.fig_esg_rosca.tight_layout(pad=2.0); self.canvas_esg_rosca = FigureCanvasTkAgg(self.fig_esg_rosca, master=esg_graf_frame); self.canvas_esg_rosca.get_tk_widget().pack(fill="both", expand=True)

    def setup_aba_balanca(self):
        self.aba_fin = tb.Frame(self.relatorios_nb, padding=12)
        self.relatorios_nb.add(self.aba_fin, text="Balança Comercial (R$)")
        fin_filtros_frame = tb.Labelframe(self.aba_fin, text="Parâmetros Financeiros", padding=10, bootstyle=INFO); fin_filtros_frame.pack(fill="x", pady=(0, 10))
        tb.Label(fin_filtros_frame, text="Data Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
        self.fin_data_inicio = CalendarioPremium(fin_filtros_frame, dateformat="%d/%m/%Y"); self.fin_data_inicio.set_date(date(2025, 1, 1)); self.fin_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,15))
        tb.Label(fin_filtros_frame, text="Data Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
        self.fin_data_fim = CalendarioPremium(fin_filtros_frame, dateformat="%d/%m/%Y"); self.fin_data_fim.set_date(datetime.now().date()); self.fin_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,15))
        self.btn_gerar_fin = tb.Button(fin_filtros_frame, text="Gerar Balanço", bootstyle=SUCCESS, command=self.calcular_balanca_comercial); self.btn_gerar_fin.grid(row=0, column=4, sticky="w", padx=(10,0))
        
        fin_cards_frame = tb.Frame(self.aba_fin); fin_cards_frame.pack(fill="x", pady=(5, 10))
        card_fin_receita = tb.Labelframe(fin_cards_frame, text=" Receita Total (R$) ", bootstyle="success", padding=15); card_fin_receita.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.lbl_fin_receita = tb.Label(card_fin_receita, text="R$ 0,00", font=("Segoe UI", 20, "bold"), bootstyle="success"); self.lbl_fin_receita.pack()
        card_fin_custo = tb.Labelframe(fin_cards_frame, text=" Custos Totais (R$) ", bootstyle="danger", padding=15); card_fin_custo.pack(side="left", fill="x", expand=True, padx=(5, 5))
        self.lbl_fin_custo = tb.Label(card_fin_custo, text="R$ 0,00", font=("Segoe UI", 20, "bold"), bootstyle="danger"); self.lbl_fin_custo.pack()
        card_fin_kpi = tb.Labelframe(fin_cards_frame, text=" Indicador Geral (R$/m²) ", bootstyle="primary", padding=15); card_fin_kpi.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.lbl_fin_kpi = tb.Label(card_fin_kpi, text="R$ 0,00 / m²", font=("Segoe UI", 20, "bold"), bootstyle="primary"); self.lbl_fin_kpi.pack()
        
        fin_content_frame = tb.Frame(self.aba_fin); fin_content_frame.pack(fill="both", expand=True); fin_content_frame.columnconfigure(0, weight=1); fin_content_frame.columnconfigure(1, weight=1)
        fin_card_tabela = tb.Labelframe(fin_content_frame, text="Detalhamento Mensal", padding=10, bootstyle=INFO); fin_card_tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        fin_cols = ("Mês", "Receita (R$)", "Custos (R$)", "Custo Real (R$)", "Produção (m²)", "Indicador (R$/m²)")
        self.fin_tbl = ttk.Treeview(fin_card_tabela, columns=fin_cols, show="headings"); self.fin_tbl.pack(side="left", fill="both", expand=True)
        for c in fin_cols: self.fin_tbl.heading(c, text=c); self.fin_tbl.column(c, anchor="center", width=85)
        fin_scroll = ttk.Scrollbar(fin_card_tabela, orient="vertical", command=self.fin_tbl.yview); self.fin_tbl.configure(yscrollcommand=fin_scroll.set); fin_scroll.pack(side="right", fill="y")
        
        fin_graf_frame = tb.Labelframe(fin_content_frame, text=" Evolução: Custos vs Receitas ", bootstyle="dark", padding=10); fin_graf_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.fig_fin, self.ax_fin = plt.subplots(figsize=(5,3)); self.fig_fin.tight_layout(pad=1.5); self.canvas_fin = FigureCanvasTkAgg(self.fig_fin, master=fin_graf_frame); self.canvas_fin.get_tk_widget().pack(fill="both", expand=True)

    def setup_aba_geracao(self):
        self.aba_geracao = tb.Frame(self.relatorios_nb, padding=12)
        self.relatorios_nb.add(self.aba_geracao, text="Geração (Rateio)")
        ger_filtros_frame = tb.Labelframe(self.aba_geracao, text="Filtro de Geração", padding=10, bootstyle=INFO); ger_filtros_frame.pack(fill="x", pady=(0, 10)); ger_filtros_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        tb.Label(ger_filtros_frame, text="Mês Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
        self.ger_data_inicio = CalendarioPremium(ger_filtros_frame, dateformat="%d/%m/%Y"); self.ger_data_inicio.set_date(date(2025, 1, 1)); self.ger_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))
        tb.Label(ger_filtros_frame, text="Mês Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
        self.ger_data_fim = CalendarioPremium(ger_filtros_frame, dateformat="%d/%m/%Y"); self.ger_data_fim.set_date(datetime.now().date()); self.ger_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))
        tb.Label(ger_filtros_frame, text="Resíduo/Grupo:").grid(row=0, column=4, sticky="e", padx=(0,5))
        self.ger_res_var = tk.StringVar()
        self.ger_res_cb = tb.Combobox(ger_filtros_frame, textvariable=self.ger_res_var, state="readonly"); self.ger_res_cb.grid(row=0, column=5, sticky="ew")
        self.btn_gerar_geracao = tb.Button(ger_filtros_frame, text="Calcular Geração Rateada", bootstyle=SUCCESS, command=self.start_geracao_calculation); self.btn_gerar_geracao.grid(row=1, column=0, columnspan=6, sticky="w", pady=(10,0))
        
        ger_resumo_frame = tb.Frame(self.aba_geracao); ger_resumo_frame.pack(fill="x", pady=(0, 10)); ger_resumo_frame.columnconfigure((0, 1), weight=1, uniform="ger_kpi")
        self.ger_kpi_total_var = tk.StringVar(value="0 kg"); self.ger_kpi_media_var = tk.StringVar(value="0,00 kg/dia")
        card_total = tb.Frame(ger_resumo_frame, bootstyle="success", relief="raised", borderwidth=1); card_total.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tb.Label(card_total, text="GERAÇÃO TOTAL (PERÍODO)", font=("Segoe UI", 8), bootstyle="success-inverse").pack(fill="x", pady=(5,0), padx=10)
        tb.Label(card_total, textvariable=self.ger_kpi_total_var, font=("Segoe UI", 16, "bold"), bootstyle="success-inverse").pack(fill="x", pady=(0,10), padx=10)
        card_media = tb.Frame(ger_resumo_frame, bootstyle="info", relief="raised", borderwidth=1); card_media.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tb.Label(card_media, text="MÉDIA DIÁRIA (ÚLTIMO CICLO)", font=("Segoe UI", 8), bootstyle="info-inverse").pack(fill="x", pady=(5,0), padx=10)
        tb.Label(card_media, textvariable=self.ger_kpi_media_var, font=("Segoe UI", 16, "bold"), bootstyle="info-inverse").pack(fill="x", pady=(0,10), padx=10)

        ger_card = tb.Labelframe(self.aba_geracao, text="Detalhamento Mensal", padding=10, bootstyle=INFO); ger_card.pack(fill="both", expand=True)
        ger_cols = ("Mês", "Coletado (kg)", "Previsão (kg)", "Total (kg)")
        self.ger_tbl = ttk.Treeview(ger_card, columns=ger_cols, show="headings", height=8); self.ger_tbl.pack(side="left", fill="both", expand=True)
        self.ger_tbl.heading("Mês", text="Mês/Ano"); self.ger_tbl.heading("Coletado (kg)", text="Resíduo coletado"); self.ger_tbl.heading("Previsão (kg)", text="Projeção Contínua (Previsão)"); self.ger_tbl.heading("Total (kg)", text="Total do Mês (kg)")
        self.ger_tbl.column("Mês", anchor="center", width=120); self.ger_tbl.column("Coletado (kg)", anchor="center", width=160); self.ger_tbl.column("Previsão (kg)", anchor="center", width=160); self.ger_tbl.column("Total (kg)", anchor="center", width=150)
        ger_scroll = ttk.Scrollbar(ger_card, orient="vertical", command=self.ger_tbl.yview); self.ger_tbl.configure(yscrollcommand=ger_scroll.set); ger_scroll.pack(side="right", fill="y")
        
        memoria_card = tb.Labelframe(self.aba_geracao, text="Memória de Cálculo (Log de Rateio)", padding=10, bootstyle=WARNING); memoria_card.pack(fill="x", pady=(10, 0))
        self.txt_memoria_geracao = tk.Text(memoria_card, height=6, wrap="word", font=("Consolas", 9)); self.txt_memoria_geracao.pack(side="left", fill="both", expand=True)
        memoria_scroll = ttk.Scrollbar(memoria_card, orient="vertical", command=self.txt_memoria_geracao.yview); self.txt_memoria_geracao.configure(yscrollcommand=memoria_scroll.set); memoria_scroll.pack(side="right", fill="y")

    def setup_aba_ecoeficiencia(self):
        self.aba_eco = tb.Frame(self.relatorios_nb, padding=12)
        self.relatorios_nb.add(self.aba_eco, text="Ecoeficiência (kg/m²)")
        eco_filtros_frame = tb.Labelframe(self.aba_eco, text="Filtros de Ecoeficiência", padding=10, bootstyle=INFO); eco_filtros_frame.pack(fill="x", pady=(0, 10)); eco_filtros_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        tb.Label(eco_filtros_frame, text="Mês Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
        self.eco_data_inicio = CalendarioPremium(eco_filtros_frame, dateformat="%d/%m/%Y"); self.eco_data_inicio.set_date(date(2025, 1, 1)); self.eco_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))
        tb.Label(eco_filtros_frame, text="Mês Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
        self.eco_data_fim = CalendarioPremium(eco_filtros_frame, dateformat="%d/%m/%Y"); self.eco_data_fim.set_date(datetime.now().date()); self.eco_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))
        tb.Label(eco_filtros_frame, text="Resíduo/Grupo:").grid(row=0, column=4, sticky="e", padx=(0,5))
        self.eco_res_var = tk.StringVar()
        self.eco_res_cb = tb.Combobox(eco_filtros_frame, textvariable=self.eco_res_var, state="readonly"); self.eco_res_cb.grid(row=0, column=5, sticky="ew")
        
        self.btn_gerar_eco = tb.Button(eco_filtros_frame, text="Calcular Indicador (kg/m²)", bootstyle=SUCCESS, command=self.calcular_ecoeficiencia); self.btn_gerar_eco.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10,0))
        self.btn_export_eco_xls = tb.Button(eco_filtros_frame, text="📊 Exportar Excel", bootstyle="outline-success", command=self.exportar_ecoeficiencia_excel); self.btn_export_eco_xls.grid(row=1, column=4, sticky="e", pady=(10,0), padx=5)
        self.btn_export_eco_pdf = tb.Button(eco_filtros_frame, text="📕 Gerar PDF", bootstyle="outline-danger", command=self.exportar_ecoeficiencia_pdf); self.btn_export_eco_pdf.grid(row=1, column=5, sticky="e", pady=(10,0))

        eco_content_frame = tb.Frame(self.aba_eco); eco_content_frame.pack(fill="both", expand=True); eco_content_frame.columnconfigure(0, weight=1); eco_content_frame.columnconfigure(1, weight=1)
        eco_card = tb.Labelframe(eco_content_frame, text="Detalhamento Mensal", padding=10, bootstyle=INFO); eco_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        eco_cols = ("Mês", "Geração (kg)", "Produção (m²)", "Indicador (kg/m²)")
        self.eco_tbl = ttk.Treeview(eco_card, columns=eco_cols, show="headings"); self.eco_tbl.pack(side="left", fill="both", expand=True)
        for c in eco_cols: self.eco_tbl.heading(c, text=c); self.eco_tbl.column(c, anchor="center", width=110)
        eco_scroll = ttk.Scrollbar(eco_card, orient="vertical", command=self.eco_tbl.yview); self.eco_tbl.configure(yscrollcommand=eco_scroll.set); eco_scroll.pack(side="right", fill="y")
        
        eco_graf_card = tb.Labelframe(eco_content_frame, text="Evolução do Indicador", padding=10, bootstyle=WARNING); eco_graf_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.fig_eco, self.ax_eco = plt.subplots(figsize=(5,3)); self.fig_eco.tight_layout(pad=1.5); self.canvas_eco = FigureCanvasTkAgg(self.fig_eco, master=eco_graf_card); self.canvas_eco.get_tk_widget().pack(fill="both", expand=True)

    def setup_aba_configuracoes(self):
        self.aba_config = tb.Frame(self.nb, padding=12)
        self.nb.add(self.aba_config, text="Configurações")
        self.config_nb = tb.Notebook(self.aba_config, bootstyle=PRIMARY)
        self.config_nb.pack(fill="both", expand=True)
        
        # ----------------------------------------------------
        # 1. ABA DE RESÍDUOS
        # ----------------------------------------------------
        self.aba_banco = tb.Frame(self.config_nb, padding=12)
        self.config_nb.add(self.aba_banco, text="Resíduos")
        
        bn_actions = tb.Frame(self.aba_banco); bn_actions.pack(fill="x")
        tb.Label(bn_actions, text="Cadastro de resíduos e valores padrão").pack(side="left")
        
        self.btn_bn_add = tb.Button(bn_actions, text="Adicionar", image=self.icons.get("add"), compound=LEFT, bootstyle=SUCCESS, command=self.banco_add)
        self.btn_bn_edit = tb.Button(bn_actions, text="Editar", image=self.icons.get("edit"), compound=LEFT, bootstyle=INFO, command=self.banco_edit_wrapper)
        self.btn_bn_del = tb.Button(bn_actions, text="Excluir", image=self.icons.get("delete"), compound=LEFT, bootstyle=DANGER, command=self.banco_del)
        self.btn_bn_reclass = tb.Button(bn_actions, text="Reclassificar Nome", bootstyle="warning", command=self.reclassificar_lote)
        self.btn_bn_lote = tb.Button(bn_actions, text="Agrupar", image=self.icons.get("edit"), compound=LEFT, bootstyle="warning", command=self.banco_edit_grupo_lote) 
        
        self.btn_bn_del.pack(side="left", padx=6)
        self.btn_bn_reclass.pack(side="left", padx=6)
        self.btn_bn_lote.pack(side="left", padx=6) 
        self.btn_bn_edit.pack(side="left", padx=6)
        self.btn_bn_add.pack(side="left", padx=0)

        # Busca por nome do resíduo
        self.bn_busca = tk.StringVar()
        self.bn_busca_entry = tb.Entry(bn_actions, textvariable=self.bn_busca, width=30)
        self.bn_busca_entry.pack(side="right", padx=(0, 6))
        tb.Label(bn_actions, text="Buscar resíduo:").pack(side="right", padx=(0, 6))
        self.bn_busca.trace_add("write", lambda *_: self.preencher_banco_tabela())

        bn_card = tb.Labelframe(self.aba_banco, text="Resíduos cadastrados", padding=6, bootstyle=INFO)
        bn_card.pack(fill="both", expand=True, pady=(10,0)); bn_card.rowconfigure(0, weight=1); bn_card.columnconfigure(0, weight=1)
        
        bn_cols = ("Resíduo (Interno)", "Nome p/ NF", "Código Item", "Modo Padrão", "Valor/kg Padrão", "Valor Fechado Padrão", "Peso/Unidade Padrão")
        self.bn_tbl = ttk.Treeview(bn_card, columns=bn_cols, show="headings", selectmode="extended")
        self.bn_tbl.grid(row=0, column=0, sticky="nsew")
        
        bn_sy = ttk.Scrollbar(bn_card, orient="vertical", command=self.bn_tbl.yview)
        self.bn_tbl.configure(yscroll=bn_sy.set); bn_sy.grid(row=0, column=1, sticky="ns")

        self.bn_tbl.heading("Resíduo (Interno)", text="Resíduo"); self.bn_tbl.column("Resíduo (Interno)", width=180, anchor="center", stretch=True)
        self.bn_tbl.heading("Nome p/ NF", text="Nome item"); self.bn_tbl.column("Nome p/ NF", width=220, anchor="center", stretch=True)
        self.bn_tbl.heading("Código Item", text="Código Item"); self.bn_tbl.column("Código Item", width=100, anchor="center", stretch=False)
        self.bn_tbl.heading("Modo Padrão", text="Modo"); self.bn_tbl.column("Modo Padrão", width=80, anchor="center", stretch=False)
        self.bn_tbl.heading("Valor/kg Padrão", text="Valor/kg (R$)"); self.bn_tbl.column("Valor/kg Padrão", width=120, anchor="center", stretch=False)
        self.bn_tbl.heading("Valor Fechado Padrão", text="Valor Fechado (R$)"); self.bn_tbl.column("Valor Fechado Padrão", width=140, anchor="center", stretch=False)
        self.bn_tbl.heading("Peso/Unidade Padrão", text="Peso/Unid. (kg)"); self.bn_tbl.column("Peso/Unidade Padrão", width=120, anchor="center", stretch=False)

        # ----------------------------------------------------
        # 2. ABA DE PARCEIROS
        # ----------------------------------------------------
        self.aba_parc = tb.Frame(self.config_nb, padding=12)
        self.config_nb.add(self.aba_parc, text="Parceiros")
        
        pc_actions = tb.Frame(self.aba_parc); pc_actions.pack(fill="x")
        tb.Label(pc_actions, text="Cadastro de parceiros").pack(side="left")
        
        self.btn_pc_add = tb.Button(pc_actions, text="Adicionar", image=self.icons.get("add"), compound=LEFT, bootstyle=SUCCESS, command=self.parceiros_add)
        self.btn_pc_edit = tb.Button(pc_actions, text="Editar", image=self.icons.get("edit"), compound=LEFT, bootstyle=INFO, command=self.parceiros_edit_wrapper)
        self.btn_pc_del = tb.Button(pc_actions, text="Excluir", image=self.icons.get("delete"), compound=LEFT, bootstyle=DANGER, command=self.parceiros_del)
        
        self.btn_pc_del.pack(side="left", padx=6)
        self.btn_pc_edit.pack(side="left", padx=6)
        self.btn_pc_add.pack(side="left", padx=0)
        
        pc_card = tb.Labelframe(self.aba_parc, text="Parceiros cadastrados", padding=6, bootstyle=INFO)
        pc_card.pack(fill="both", expand=True, pady=(10,0)); pc_card.rowconfigure(0, weight=1); pc_card.columnconfigure(0, weight=1)
        
        pc_cols = ("Parceiro", "Tipo")
        self.pc_tbl = ttk.Treeview(pc_card, columns=pc_cols, show="headings", selectmode="browse")
        self.pc_tbl.grid(row=0, column=0, sticky="nsew")
        
        pc_sy = ttk.Scrollbar(pc_card, orient="vertical", command=self.pc_tbl.yview)
        self.pc_tbl.configure(yscroll=pc_sy.set); pc_sy.grid(row=0, column=1, sticky="ns")
        
        self.pc_tbl.heading("Parceiro", text="Nome do Parceiro"); self.pc_tbl.column("Parceiro", width=100, anchor="center", stretch=True)
        self.pc_tbl.heading("Tipo", text="Tipo"); self.pc_tbl.column("Tipo", width=100, anchor="center", stretch=True)
        self.pc_tbl.bind("<Delete>", lambda e: self.parceiros_del()) 

        # ----------------------------------------------------
        # 3. OUTRAS SUB-ABAS (Feriados, Metragem, etc)
        # ----------------------------------------------------
        self.aba_feriados_config = tb.Frame(self.config_nb, padding=12)
        self.config_nb.add(self.aba_feriados_config, text="Feriados e Férias")
        frame_info_feriados = tb.Labelframe(self.aba_feriados_config, text="Gerenciamento de Paradas", padding=20, bootstyle=INFO)
        frame_info_feriados.pack(fill="x", pady=10)
        tb.Label(frame_info_feriados, text="Adicione aqui os dias em que a empresa não opera (Férias coletivas, feriados emendados, etc).\nO sistema usará essas datas para descontar automaticamente dos cálculos de média e rateio.").pack(anchor="w", pady=(0, 15))
        tb.Button(frame_info_feriados, text="📅 Abrir Painel de Feriados", bootstyle="primary", command=lambda: abrir_gestao_feriados(self.root), width=30).pack(anchor="w")

    # ==============================================================================
    # LÓGICA DE INTERFACE DINÂMICA
    # ==============================================================================
    def alternar_tema(self):
        novo = "superhero" if self.style.theme.name != "superhero" else "yeti"
        self.style.theme_use(novo)
        self.config_tags_por_tema()
        self.atualizar_dashboard_home()
        df_filtrado_atual = self.aplicar_filtros(self.df_registros.copy())
        self.preencher_tabela(df_filtrado_atual)
        self.set_status(f"Tema: {novo}")

    def config_tags_por_tema(self):
        dark = (self.style.theme.name == "superhero")
        dark_solido_bg="#1f3a2e"; dark_liquido_bg="#1a2e4a"
        light_solido_bg="#e8f8ee"; light_liquido_bg="#e8f1fb"
        dark_alert_bg = "#4a1a1a"; light_alert_bg = "#ffe6e6" 
        
        font_normal = ("TkDefaultFont", 9); font_bold = ("TkDefaultFont", 9, "bold")

        if dark:
            self.tabela.tag_configure("estado_solido", background=dark_solido_bg)
            self.tabela.tag_configure("estado_liquido", background=dark_liquido_bg)
            self.tabela.tag_configure("cert_ok", foreground="white", font=font_normal)
            self.tabela.tag_configure("cert_nao", foreground="#FF6347", font=font_bold)
            self.tabela.tag_configure("nf_ok", foreground="white", font=font_normal)
            self.tabela.tag_configure("nf_nao", foreground="#FF6347", font=font_bold)
            self.tabela.tag_configure("tipo_venda", foreground="#28a745")
            self.tabela.tag_configure("tipo_custo", foreground="#dc3545", font=font_bold)
            self.tabela.tag_configure("atrasado", background=dark_alert_bg) 
            self.resumo_tbl.tag_configure("lucro_pos", foreground="#28a745") 
            self.resumo_tbl.tag_configure("lucro_neg", foreground="#ff4d4d") 
            self.style.configure("Treeview", background=self.style.colors.bg) 
            self.style.map("Treeview", background=[('selected', self.style.colors.primary)])
            for tv in [self.tabela, self.resumo_tbl, self.pend_tbl, self.bn_tbl, self.pc_tbl, self.bana_tbl]:
                tv.tag_configure("oddrow", background=self.style.colors.bg) 
                tv.tag_configure("evenrow", background="#2a2a2a")
        else:
            self.tabela.tag_configure("estado_solido", background=light_solido_bg)
            self.tabela.tag_configure("estado_liquido", background=light_liquido_bg)
            self.tabela.tag_configure("cert_ok", foreground="black", font=font_normal)
            self.tabela.tag_configure("cert_nao", foreground="#CC0000", font=font_bold)
            self.tabela.tag_configure("nf_ok", foreground="black", font=font_normal)
            self.tabela.tag_configure("nf_nao", foreground="#CC0000", font=font_bold)
            self.tabela.tag_configure("tipo_venda", foreground="#155724")
            self.tabela.tag_configure("tipo_custo", foreground="#721c24", font=font_bold)
            self.tabela.tag_configure("atrasado", background=light_alert_bg)
            self.resumo_tbl.tag_configure("lucro_pos", foreground="#155724") 
            self.resumo_tbl.tag_configure("lucro_neg", foreground="#cc0000") 
            self.style.configure("Treeview", background=self.style.colors.bg) 
            self.style.map("Treeview", background=[('selected', self.style.colors.primary)]) 
            for tv in [self.tabela, self.resumo_tbl, self.pend_tbl, self.bn_tbl, self.pc_tbl, self.bana_tbl]:
                tv.tag_configure("oddrow", background=self.style.colors.bg) 
                tv.tag_configure("evenrow", background="#f2f2f2")

    def toggle_campos_por_modo(self, *_args):
        modo = clean_str(self.calc_mode_var.get()).lower()
        for w in [self.label_valor_kg, self.entrada_valor_kg, self.label_valor_fechado, self.entrada_valor_fechado,
                  self.label_peso_unitario, self.entrada_peso_unitario, self.label_peso_kg, self.entrada_peso_kg]:
            w.grid_remove()

        if modo not in ("kg", "unidade"): self.entrada_valor_kg.delete(0, tk.END)
        if modo != "fechado": self.entrada_valor_fechado.delete(0, tk.END)
        if modo != "unidade":
            self.peso_unitario_var.set("")
            self.peso_kg_var.set("")

        if modo == "kg":
            self.label_valor_kg.config(text="Valor por kg (R$)"); self.label_valor_kg.grid(); self.entrada_valor_kg.grid()
            self.label_peso.config(text="Peso (kg)", bootstyle=INFO)
        elif modo == "unidade":
            self.label_valor_kg.config(text="Valor Unitário (R$)"); self.label_valor_kg.grid(); self.entrada_valor_kg.grid()
            self.label_peso.config(text="Quantidade (unid.)", bootstyle=INFO)
            self.label_peso_unitario.grid(); self.entrada_peso_unitario.grid()
            self.label_peso_kg.config(text="Peso Total (kg)", bootstyle=SUCCESS); self.label_peso_kg.grid(); self.entrada_peso_kg.grid()
        elif modo == "fechado":
            self.label_valor_fechado.grid(); self.entrada_valor_fechado.grid()
            self.label_peso.config(text="Peso (kg) [Obrigatório]", bootstyle=WARNING)

        self.calcular_resumo_financeiro_automatico()

    def toggle_pedido_por_tipo(self, *_args):
        is_custo = clean_str(self.tipo_var.get()).lower() == "custo"
        self.entrada_pedido.configure(state=("normal" if is_custo else "disabled"))
        if not is_custo: self.entrada_pedido.delete(0, tk.END)

    def toggle_launch_view(self, *_args):
        tipo = self.launch_type_var.get()
        self.cad.pack_forget(); self.cad_actions.pack_forget()
        self.frm_ana.pack_forget(); self.btn_ana_add.pack_forget()
        self.frm_transporte.pack_forget()
        
        if tipo == "Resíduo":
            destinacoes_residuo = [d for d in self.destinacoes if d != "Análise externa"]
            self.destinacao_cb.configure(values=destinacoes_residuo)
            if self.destinacao_var.get() == "Análise externa":
                self.destinacao_var.set(destinacoes_residuo[0] if destinacoes_residuo else "")
            self.cad.pack(fill="x"); self.cad_actions.pack(fill="x", pady=(5,0))
            
        elif tipo == "Análise":
            self.frm_ana.pack(fill="x", pady=(0, 0)); self.btn_ana_add.pack(pady=15, anchor="w")
            
        elif tipo == "Transporte":
            self.transp_parc_cb.configure(values=self.parceiros)
            self.transp_res_cb.configure(values=self.banco_residuos)
            self.frm_transporte.pack(fill="x", pady=(0, 0))

    def atualizar_form_por_residuo(self, *_args):
        nome_residuo = clean_str(self.res_var.get())
        dados = self.banco_dict.get(nome_residuo)

        self.peso_unitario_var.set("")
        self.peso_kg_var.set("")

        if dados:
            modo = dados.get('modo', 'kg')
            val_kg = dados.get('kg', 0.0)
            val_fec = dados.get('fechado', 0.0)
            val_pu = dados.get('peso_unitario', 0.0)

            self.calc_mode_var.set(modo)
            self.root.after(50, lambda: self.preencher_valor_residuo(modo, val_kg, 0.0, val_fec))
            
            if modo == 'unidade' and val_pu > 0:
                 s_pu = f"{val_pu:.3f}".replace(".", ",").rstrip("0").rstrip(",")
                 self.root.after(55, lambda: self.peso_unitario_var.set(s_pu))

            p_estado = dados.get('estado_padrao'); 
            if p_estado: self.estado_var.set(p_estado)
            p_dest = dados.get('destinacao_padrao'); 
            if p_dest: self.destinacao_var.set(p_dest)
            p_tipo = dados.get('tipo_padrao'); 
            if p_tipo: self.tipo_var.set(p_tipo)
            p_parc = dados.get('parceiro_padrao'); 
            if p_parc: self.parceiro_var.set(p_parc)
            
            padrao_nf = dados.get('exige_nf', True)
            padrao_cert = dados.get('exige_cert', True)
            self.var_nf_manual.set(1 if padrao_nf else 0)
            self.var_cert_manual.set(1 if padrao_cert else 0)
        else:
            self.calc_mode_var.set('kg')
            self.root.after(50, lambda: self.entrada_valor_kg.delete(0, tk.END))
            self.var_nf_manual.set(1); self.var_cert_manual.set(1)

    def preencher_valor_residuo(self, modo, val_kg, val_ton, val_fec): 
        self.entrada_valor_kg.delete(0, tk.END)
        self.entrada_valor_fechado.delete(0, tk.END)
        val_kg_dec = Decimal(str(val_kg)); val_fec_dec = Decimal(str(val_fec))

        if modo in ('kg', 'unidade') and val_kg_dec > Decimal('0'):
            self.entrada_valor_kg.insert(0, f"{val_kg_dec:.3f}".replace(".", ",").rstrip("0").rstrip(","))
        elif modo == 'fechado' and val_fec_dec > Decimal('0'):
            self.entrada_valor_fechado.insert(0, f"{val_fec_dec:.2f}".replace(".", ","))
        self.calcular_resumo_financeiro_automatico()

    def calcular_peso_kg_automatico(self, *_args):
        modo = clean_str(self.calc_mode_var.get()).lower()
        if modo != "unidade":
            self.peso_kg_var.set("") 
        else:
            try:
                quantidade = money_pt(self.peso_var.get())
                peso_unitario = money_pt(self.peso_unitario_var.get())
                if quantidade > 0 and peso_unitario > 0:
                    total_kg = quantidade * peso_unitario
                    self.peso_kg_var.set(f"{total_kg:.3f}".replace(".", ",").rstrip("0").rstrip(","))
                else: self.peso_kg_var.set("") 
            except: self.peso_kg_var.set("Erro")
        self.calcular_resumo_financeiro_automatico()

    def calcular_resumo_financeiro_automatico(self, *_args):
        try:
            modo = clean_str(self.calc_mode_var.get()).lower()
            v_transporte = money_pt(self.entrada_transporte.get())
            valor_base = Decimal("0")
            
            if modo == "kg" or modo == "unidade":
                v_unit = money_pt(self.entrada_valor_kg.get())
                qtd = money_pt(self.peso_var.get())
                valor_base = v_unit * qtd
            elif modo == "fechado":
                valor_base = money_pt(self.entrada_valor_fechado.get())
                
            total_final = valor_base + v_transporte
            tipo = clean_str(self.tipo_var.get()).lower()
            
            if tipo == "venda": self.lbl_total_operacao.config(text=f"{fmt_moeda(total_final)}", bootstyle="success")
            else: self.lbl_total_operacao.config(text=f"{fmt_moeda(total_final)}", bootstyle="danger")
        except:
            self.lbl_total_operacao.config(text="R$ 0,00", bootstyle="secondary")

    def atualizar_combobox_parceiro_dinamico(self, *_args):
        modo = clean_str(self.launch_type_var.get()).lower()
        if "transporte" in modo: nova_lista = self.lista_transportadores if self.lista_transportadores else self.lista_todos_parceiros
        elif "análise" in modo or "analise" in modo: nova_lista = self.lista_laboratorios if self.lista_laboratorios else self.lista_todos_parceiros
        else: nova_lista = self.lista_destinadores if self.lista_destinadores else self.lista_todos_parceiros
                
        self.parceiro_cb.configure(values=nova_lista)
        if self.parceiro_cb.get() not in nova_lista and nova_lista: self.parceiro_cb.set(nova_lista[0])
        elif not nova_lista: self.parceiro_cb.set("")

    def atualizar_valor_por_analise(self, *_args):
        nome_analise = clean_str(self.ana_nome_var.get())
        valor_padrao = self.analises_dict.get(nome_analise, 0.0)
        self.ana_valor_fechado.delete(0, tk.END)
        if valor_padrao > 0: self.ana_valor_fechado.insert(0, f"{valor_padrao:.2f}".replace(".", ","))

    # ==============================================================================
    # ATUALIZAÇÃO DE INTERFACE E BANCOS
    # ==============================================================================
    def atualizar_views(self):
        try:
            self.df_registros = db.get_all_registros_df(data_inicio=self.DATA_CORTE_ISO)
            
            self.preencher_banco_tabela()
            self.preencher_parceiros_tabela()
            self.preencher_analises_tabela()
            self.sincronizar_residuos_ui()
            self.sincronizar_parceiros_ui()
            self.sincronizar_analises_ui()
            self.sincronizar_destinacoes_ui()
            
            df_filtrado = self.aplicar_filtros(self.df_registros.copy())
            self.preencher_tabela(df_filtrado)
            
            self.atualizar_menus_dinamicos(self.df_registros)
            self.preencher_pendencias()
            self.atualizar_dashboard_home()
            self.atualizar_eventos_calendario()
        except Exception as e:
            ModernMessageBox.showerror("Erro Crítico", f"Falha ao atualizar dados/interface: {e}")

    def clear_form(self, *_args):
        """Limpa o formulário de cadastro de resíduos."""
        self.editing_id = None

        if hasattr(self, 'lbl_total_operacao'):
            self.lbl_total_operacao.config(text="R$ 0,00", bootstyle="secondary")
            
        self.entrada_valor_kg.delete(0, tk.END)
        self.entrada_valor_fechado.delete(0, tk.END)
        self.entrada_peso.delete(0, tk.END) 
        self.peso_var.set("") 
        self.peso_unitario_var.set("")
        self.peso_kg_var.set("") 
        self.entrada_transporte.delete(0, tk.END)
        self.entrada_pedido.delete(0, tk.END)

        self.res_var.set("") 
        self.calc_mode_var.set("kg")

        self.btn_submit.configure(text="Adicionar Registro", bootstyle=SUCCESS)
        self.btn_clear_form.configure(text="Limpar Formulário", bootstyle=PRIMARY)
        
        self.root.after(10, self.toggle_campos_por_modo)
        self.root.after(10, self.toggle_pedido_por_tipo)

        self.caminho_anexo_temp.set("")
        self.lbl_anexo_info.config(text="")

    def abrir_janela_lote(self):
        """Abre janela para lançar histórico em lote com layout limpo e organizado."""
        lote_win = tb.Toplevel(self.root)
        lote_win.title("Lançamento de Histórico (Lote)")
        lote_win.geometry("1200x750") 
        
        itens_da_carga = []

        # ===========================
        # 1. DADOS FIXOS (CABEÇALHO)
        # ===========================
        frame_comum = tb.Labelframe(lote_win, text="1. Dados Fixos (Parceiro/Destinação)", padding=15, bootstyle=INFO)
        frame_comum.pack(fill="x", padx=15, pady=15)
        frame_comum.columnconfigure((0,1,2,3), weight=1)

        tb.Label(frame_comum, text="Parceiro:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        parc_cb = tb.Combobox(frame_comum, values=self.parceiros, state="readonly")
        if self.parceiros: parc_cb.current(0)
        parc_cb.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        tb.Label(frame_comum, text="Destinação:", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5)
        dest_cb = tb.Combobox(frame_comum, values=self.destinacoes, state="readonly")
        if self.destinacoes: dest_cb.current(0)
        dest_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 5))
        
        tb.Label(frame_comum, text="Tipo:", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
        tipo_cb = tb.Combobox(frame_comum, values=["Venda", "Custo"], state="readonly")
        tipo_cb.set("Venda")
        tipo_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 5))
        
        tb.Label(frame_comum, text="Pedido/Ticket (Opcional):").grid(row=0, column=3, sticky="w", padx=5)
        pedido_entry = tb.Entry(frame_comum)
        pedido_entry.grid(row=1, column=3, sticky="ew", padx=5, pady=(0, 5))

        # ===========================
        # 2. ADICIONAR ITEM (ÁREA DE TRABALHO)
        # ===========================
        frame_item = tb.Labelframe(lote_win, text="2. Adicionar Item", padding=15, bootstyle=SUCCESS)
        frame_item.pack(fill="x", padx=15, pady=5)
        frame_item.columnconfigure((0,1,2,3,4), weight=1)
        frame_item.columnconfigure(5, weight=0)
        
        tb.Label(frame_item, text="Selecione o Resíduo:", font=("Segoe UI", 10, "bold"), bootstyle="primary").grid(row=0, column=0, columnspan=6, sticky="w", padx=5)
        res_lote_var = tk.StringVar()
        res_lote_cb = tb.Combobox(frame_item, textvariable=res_lote_var, values=self.banco_residuos, state="readonly", font=("Segoe UI", 10))
        res_lote_cb.grid(row=1, column=0, columnspan=6, sticky="ew", padx=5, pady=(5, 15))
        
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

        qtd_entry = tb.Entry(frame_item, validate="key", validatecommand=self.vcmd_numeric)
        qtd_entry.grid(row=3, column=2, sticky="ew", padx=5, pady=(0, 5))
        
        valor_entry = tb.Entry(frame_item, validate="key", validatecommand=self.vcmd_numeric)
        valor_entry.grid(row=3, column=3, sticky="ew", padx=5, pady=(0, 5))

        item_preview_var = tk.StringVar(value="R$ 0,00")

        def atualizar_preview_item(*args):
            try:
                qtd_str = qtd_entry.get()
                val_str = valor_entry.get()
                if not qtd_str or not val_str:
                    item_preview_var.set("R$ 0,00")
                    return
                qtd = money_pt(qtd_str)
                val_in = money_pt(val_str)
                modo = modo_lote_var.get()
                total_fin = val_in if modo == 'fechado' else qtd * val_in
                item_preview_var.set(fmt_moeda(total_fin))
            except:
                item_preview_var.set("R$ 0,00")

        qtd_entry.bind("<KeyRelease>", atualizar_preview_item)
        valor_entry.bind("<KeyRelease>", atualizar_preview_item)
        modo_lote_var.trace_add("write", atualizar_preview_item)
        
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
        tb.Checkbutton(frame_bottom, text="Exige NF", variable=var_nf_lote, bootstyle="round-toggle").pack(side="left", padx=10)
        tb.Checkbutton(frame_bottom, text="Exige Certificado", variable=var_cert_lote, bootstyle="round-toggle").pack(side="left", padx=10)
        
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
            dados = self.banco_dict.get(nome)
            if dados:
                modo_padrao = dados.get('modo', 'kg')
                modo_lote_var.set(modo_padrao)
                val_kg = dados.get('kg', 0.0)
                val_fec = dados.get('fechado', 0.0)
                valor_entry.delete(0, tk.END)
                if modo_padrao == 'fechado' and val_fec > 0: valor_entry.insert(0, f"{val_fec:.2f}".replace(".", ","))
                elif val_kg > 0: valor_entry.insert(0, f"{val_kg:.4f}".replace(".", ","))
                est = dados.get('estado_padrao')
                if est: estado_lote_var.set(est)
                var_nf_lote.set(1 if dados.get('exige_nf', True) else 0)
                var_cert_lote.set(1 if dados.get('exige_cert', True) else 0)
                peso_u = dados.get('peso_unitario', 0.0)
                if modo_padrao == 'unidade': info_lbl.config(text=f"ℹ Peso Referência: {peso_u} kg/un")
                else: info_lbl.config(text="")

        res_lote_cb.bind("<<ComboboxSelected>>", ao_selecionar_residuo)

        def adicionar_item_lista():
            try:
                d_item = obter_data_segura(dt_item_entry)
                data_str = d_item.strftime("%Y-%m-%d")
                data_view = d_item.strftime("%d/%m/%y")
            except: ModernMessageBox.showerror("Erro", "Data inválida."); return

            residuo = res_lote_var.get()
            qtd_str = qtd_entry.get()
            val_str = valor_entry.get()
            if not residuo or not qtd_str: ModernMessageBox.showwarning("Aviso", "Preencha dados."); return
                
            qtd = money_pt(qtd_str)
            val_in = money_pt(val_str)
            modo = modo_lote_var.get()
            
            dados = self.banco_dict.get(residuo, {})
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
                "peso_calc": float(peso_real), "nf_ok": nf_status, "cert_ok": cert_status
            }
            itens_da_carga.append(item_data)
            tree_lote.insert("", "end", values=(data_view, residuo, modo, disp_qtd, fmt_moeda(total_fin), nf_status, cert_status))
            
            qtd_entry.delete(0, tk.END)
            atualizar_preview_item()
            dt_item_entry.focus_set()

        btn_add.configure(command=adicionar_item_lista)
        qtd_entry.bind("<Return>", lambda e: adicionar_item_lista())
        valor_entry.bind("<Return>", lambda e: adicionar_item_lista())

        # ===========================
        # 3. LISTA VISUAL
        # ===========================
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
            if not itens_da_carga: ModernMessageBox.showwarning("Vazio", "Adicione itens."); return
            parc = parc_cb.get(); dest = dest_cb.get(); tip = tipo_cb.get(); ped = pedido_entry.get()
            if not parc or not dest: ModernMessageBox.showerror("Erro", "Parceiro/Destino obrigatórios."); return

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
                ModernMessageBox.showinfo("Sucesso", f"{sucessos} registros salvos!")
                lote_win.destroy()
                self.atualizar_views()
            else:
                ModernMessageBox.showerror("Erro", "Nenhum registro foi salvo.")

        tb.Separator(lote_win).pack(fill="x", padx=15, pady=(15, 5))
        tb.Label(lote_win, textvariable=item_preview_var, font=("Segoe UI", 18, "bold"), bootstyle="success").pack(anchor="e", padx=30, pady=(0, 15))
        tb.Button(lote_win, text="CONCLUIR E SALVAR TUDO", bootstyle="success", width=30, command=salvar_carga_banco).pack(fill="x", padx=30, pady=(0,20))

    def clear_form_analise(self, *_args):
        """Limpa o formulário de Análises."""
        self.editing_id = None
        if hasattr(self, 'ana_parc_var'): self.ana_parc_var.set("")
        if hasattr(self, 'ana_nome_var'): self.ana_nome_var.set("")
        if hasattr(self, 'ana_valor_fechado'): self.ana_valor_fechado.delete(0, tk.END)
        if hasattr(self, 'ana_pedido'): self.ana_pedido.delete(0, tk.END)
        if hasattr(self, 'btn_ana_add'):
            self.btn_ana_add.configure(text="Adicionar análise (custo)", bootstyle=SUCCESS)
            if hasattr(self.btn_ana_add, 'editing_id'):
                del self.btn_ana_add.editing_id

    def adicionar_analise_event(self, _=None):
        """Lógica para salvar/editar registro de Análise Externa."""
        try:
            data_str = obter_data_segura(self.ana_data).strftime("%Y-%m-%d")
        except Exception:
            ModernMessageBox.showerror("Erro", "Data inválida."); return

        parceiro = clean_str(self.ana_parc_var.get())
        nome_analise = clean_str(self.ana_nome_var.get())
        val_str = self.ana_valor_fechado.get()
        valor_total = money_pt(val_str)
        pedido = clean_str(self.ana_pedido.get())

        if not parceiro: ModernMessageBox.showwarning("Aviso", "Selecione o Laboratório/Parceiro."); return
        if not nome_analise: ModernMessageBox.showwarning("Aviso", "Selecione o Nome da Análise."); return
        if valor_total <= 0: ModernMessageBox.showwarning("Aviso", "O valor deve ser maior que zero."); return

        if not nome_analise.startswith("[ANÁLISE]"): residuo_final = f"[ANÁLISE] {nome_analise}"
        else: residuo_final = nome_analise

        nf_status = "Não" if self.var_nf_ana.get() else "N/A"
        cert_status = "Não" if self.var_cert_ana.get() else "N/A"

        editing_id = getattr(self.btn_ana_add, 'editing_id', None)
        if editing_id is None and self.editing_id is not None:
            if self.launch_type_var.get() == "Análise":
                editing_id = self.editing_id

        if editing_id is not None:
            try:
                val_antigo_nf = self.df_registros.loc[editing_id, 'NFOk']
                if nf_status == "Não" and val_antigo_nf not in ("N/A", "n/a"): nf_status = val_antigo_nf
                val_antigo_cert = self.df_registros.loc[editing_id, 'CertificadoOK']
                if cert_status == "Não" and val_antigo_cert not in ("N/A", "n/a"): cert_status = val_antigo_cert
            except: pass

        registro_analise = [
            data_str, parceiro, residuo_final, "N/A", "Análise externa", "Custo", "fechado",
            0.0, 0.0, float(valor_total), 0.0, float(valor_total), pedido, "", cert_status, 0.0, nf_status, ""
        ]

        try:
            if editing_id is not None:
                if db.update_registro(editing_id, registro_analise):
                    if hasattr(db, 'update_nf'): db.update_nf(editing_id, nf_status)
                    self.set_status("Análise atualizada com sucesso.")
                else: ModernMessageBox.showerror("Erro", "Falha ao atualizar registro no banco.")
            else:
                rec_id = db.add_registro(registro_analise)
                if rec_id and rec_id != -1:
                    if hasattr(db, 'update_nf'): db.update_nf(rec_id, nf_status)
                    self.set_status("Análise adicionada com sucesso.")
                else: ModernMessageBox.showerror("Erro", "Falha ao salvar registro no banco.")

            self.clear_form_analise()
            self.atualizar_views()
            if editing_id is not None: self.nb.select(self.aba_regs)
        except Exception as e:
            ModernMessageBox.showerror("Erro Crítico", f"Erro ao salvar análise: {e}")

    def adicionar_transporte_event(self, _=None):
        """Lógica para salvar registro de Frete."""
        try:
            data_obj = obter_data_segura(self.transp_data)
            data_str = data_obj.strftime("%Y-%m-%d")
        except Exception:
            ModernMessageBox.showerror("Erro", "Data inválida."); return

        parceiro = clean_str(self.transp_parc_var.get())
        residuo_base = clean_str(self.transp_res_var.get())
        valor_frete = money_pt(self.transp_valor.get())
        pedido = clean_str(self.transp_pedido.get())

        if not parceiro: ModernMessageBox.showwarning("Aviso", "Selecione a Transportadora/Parceiro."); return
        if not residuo_base: ModernMessageBox.showwarning("Aviso", "Selecione o Resíduo atrelado ao frete."); return
        if valor_frete <= 0: ModernMessageBox.showwarning("Aviso", "O valor do frete deve ser maior que zero."); return

        dados_res = self.banco_dict.get(residuo_base, {})
        estado_auto = dados_res.get('estado_padrao', 'Sólido')
        destinacao_auto = dados_res.get('destinacao_padrao', 'N/A')

        nome_final = f"[FRETE] {residuo_base}"
        nf_status = "Não" if self.var_nf_transp.get() else "N/A"
        cert_status = "Não" if self.var_cert_transp.get() else "N/A"

        transporte_data = [
            data_str, parceiro, nome_final, estado_auto, destinacao_auto, "Custo", "fechado",
            0.0, 0.0, 0.0, float(valor_frete), float(valor_frete), pedido, "", cert_status, 0.0, nf_status, ""
        ]

        try:
            rec_id = db.add_registro(transporte_data)
            if rec_id is not None and rec_id > 0:
                if hasattr(db, 'update_nf'): db.update_nf(rec_id, nf_status)
                self.atualizar_views()
                self.transp_valor.delete(0, tk.END)
                self.transp_pedido.delete(0, tk.END)
                self.set_status("Frete adicionado com sucesso.")
                ModernMessageBox.showinfo("Sucesso", "Frete lançado!")
            else:
                ModernMessageBox.showerror("Erro de Banco de Dados", "Não foi possível salvar o registro.")
        except Exception as e:
            ModernMessageBox.showerror("Erro Crítico", f"Erro ao adicionar transporte: {e}")

    def atualizar_dashboard_home(self):
        """Calcula os KPIs do mês atual e atualiza os Cards da tela inicial."""
        try:
            hoje = date.today()
            if self.df_registros.empty:
                if hasattr(self, 'lbl_dash_peso'):
                    self.lbl_dash_peso.config(text="0,00 kg")
                    self.lbl_dash_custo.config(text="R$ 0,00")
                    self.lbl_dash_rec.config(text="0,0%")
                return

            df = get_df_com_peso_real(self.df_registros.copy())
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            df_mes = df[(df['Data'].dt.month == hoje.month) & (df['Data'].dt.year == hoje.year)]
            
            peso_total = df_mes['Peso_KG_Real'].sum() if 'Peso_KG_Real' in df_mes.columns else 0.0
            custo_total = df_mes['ValorTotal'].sum() if 'ValorTotal' in df_mes.columns else 0.0
            
            palavras_verdes = ['reciclagem', 'compostagem', 'reuso', 'blendagem para co-processamento', 'coprocessamento', 'recuperação', 'logística reversa']
            
            def verifica_circularidade(dest):
                d = str(dest).lower()
                if 'efluente' in d or 'aterro' in d or 'incineração' in d: return False
                return any(pv in d for pv in palavras_verdes)

            if not df_mes.empty:
                mask_verde = df_mes['Destinacao'].apply(verifica_circularidade)
                peso_circular = df_mes[mask_verde]['Peso_KG_Real'].sum()
            else: peso_circular = 0.0
                
            taxa_circ = (peso_circular / peso_total) * 100 if peso_total > 0 else 0.0

            peso_str = f"{peso_total:,.2f} kg".replace(",", "X").replace(".", ",").replace("X", ".")
            custo_str = f"R$ {custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            if hasattr(self, 'lbl_dash_peso'):
                self.lbl_dash_peso.config(text=peso_str)
                self.lbl_dash_custo.config(text=custo_str)
                self.lbl_dash_rec.config(text=f"{taxa_circ:.1f}%")
        except Exception:
            pass

    def atualizar_eventos_calendario(self):
        """Pinta os dias no calendário que possuem registros."""
        try:
            if not hasattr(self, 'cal_visual'): return
            self.cal_visual.calevent_remove("all") 
            if self.df_registros.empty: return

            df_temp = self.df_registros.copy()
            df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
            df_temp = df_temp.dropna(subset=['Data'])
            
            datas_unicas = df_temp['Data'].dt.date.unique()
            for d in datas_unicas:
                self.cal_visual.calevent_create(d, "Movimentação", "coleta")
            
            self.cal_visual.tag_config("coleta", background="#d1e7dd", foreground="black")
        except Exception: 
            pass

    # ==============================================================================
    # MÉTODOS DO CALENDÁRIO
    # ==============================================================================
    def atualizar_titulo_mes(self, event=None):
        """Atualiza o label com o mês e ano atualmente exibidos no calendário."""
        try:
            m, y = self.cal_visual.get_displayed_month()
            meses_abrev = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
            nome_mes = meses_abrev[m-1]
            self.titulo_mes_var.set(f"{nome_mes}/{y}")
        except Exception: 
            pass

    def navegar_calendario(self, delta):
        """Avança ou retrocede os meses no calendário visual."""
        try:
            m, y = self.cal_visual.get_displayed_month()
            m += delta
            if m > 12: 
                m = 1; y += 1
            elif m < 1: 
                m = 12; y -= 1
            self.cal_visual.see(date(y, m, 1))
            self.atualizar_titulo_mes()
        except Exception:
            pass

    def ir_para_hoje(self):
        """Volta o calendário para o dia atual."""
        try:
            hoje = datetime.now().date()
            self.cal_visual.see(hoje)
            self.cal_visual.selection_set(hoje)
            self.on_cal_click(None)
            self.atualizar_titulo_mes()
        except Exception:
            pass

    def on_cal_click(self, event=None):
        """Exibe na tabela ao lado os detalhes do dia clicado no calendário."""
        try:
            data_sel_str = self.cal_visual.get_date() 
        except:
            return
            
        for r in self.cal_tree.get_children(): 
            self.cal_tree.delete(r)
            
        self.lbl_soma_cal.config(text="Total Selecionado: R$ 0,00")
        
        try:
            dt_sel = datetime.strptime(data_sel_str, "%d/%m/%Y").date()
            df_temp = self.df_registros.copy()
            df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
            
            itens_do_dia = df_temp[df_temp['Data'].dt.date == dt_sel]
            
            if itens_do_dia.empty: return
            
            for _, row in itens_do_dia.iterrows():
                peso_input = to_float_safe(row.get("Peso", 0))
                peso_real_kg = to_float_safe(row.get("PesoEmKg", 0))
                modo = str(row.get("Modo", "kg")).lower()
                
                if modo == 'unidade':
                    if peso_real_kg > 0:
                        p_display = f"{peso_input:.0f} un ({fmt_kg(peso_real_kg)})"
                    else:
                        p_display = f"{peso_input:.0f} un"
                else:
                    p_display = fmt_kg(peso_input)
                
                valor_total = to_float_safe(row.get("ValorTotal", 0.0))
                v_display = fmt_moeda(valor_total)

                self.cal_tree.insert("", "end", values=(
                    clean_str(row.get("Residuo", "")), 
                    clean_str(row.get("Parceiro", "")), 
                    p_display,   
                    v_display, 
                    clean_str(row.get("Tipo", ""))
                ))
                
        except Exception as e: 
            print(f"Erro ao carregar detalhes do dia: {e}")

    def somar_selecao_calendario(self, event=None):
        """Soma os valores das linhas selecionadas na tabela do calendário."""
        selection = self.cal_tree.selection()
        soma = Decimal("0.00")
        
        for iid in selection:
            valores = self.cal_tree.item(iid)['values']
            val_str = str(valores[3]).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
            try:
                soma += Decimal(val_str)
            except:
                pass
                
        self.lbl_soma_cal.config(text=f"Total Selecionado: {fmt_moeda(soma)}")

    # ==============================================================================
    # MÉTODOS DA TABELA DE REGISTROS E PENDÊNCIAS
    # ==============================================================================
    def atualizar_resumo_selecao(self, event=None):
        """Calcula e exibe a soma de Peso e Valor dos itens selecionados na tabela."""
        if not hasattr(self, 'resumo_selecao_var'): return
        
        selected_iids = self.tabela.selection()
        if not selected_iids:
            self.resumo_selecao_var.set("")
            return
        
        total_peso = Decimal("0")
        total_valor = Decimal("0")
        
        for iid_str in selected_iids:
            try:
                record_id = int(iid_str)
                row_data = self.df_registros.loc[record_id]
                total_valor += _dec(row_data.get("ValorTotal", 0.0))
                modo = clean_str(row_data.get('Modo', 'kg')).lower()
                
                if modo == 'unidade':
                    total_peso += _dec(row_data.get('PesoEmKg', 0.0))
                else:
                    total_peso += _dec(row_data.get('Peso', 0.0))
            except: continue
        
        s_peso = fmt_kg(total_peso)
        s_valor = fmt_moeda(total_valor)
        count = len(selected_iids)
        self.resumo_selecao_var.set(f"Seleção: {count} {'item' if count == 1 else 'itens'} | Total Peso: {s_peso} | Total Valor: {s_valor}")

    def ordenar_coluna(self, col, reverse):
        """Ordena a tabela principal pela coluna clicada."""
        data = [(self.tabela.set(k, col), k) for k in self.tabela.get_children("")]
        def to_key(v):
            v_str = str(v)
            if col in ("Peso", "Valor por kg", "Valor fechado", "Transporte", "Valor Total"):
                s = v_str.replace("R$","").replace("kg","").replace(" ","").replace(".","").replace(",",".")
                try: return float(s)
                except ValueError: return 0.0
            elif col == "Data":
                try: return datetime.strptime(v_str, "%d/%b/%y")
                except ValueError: return datetime.min
            return v_str.lower()
        
        try: data.sort(key=lambda x: to_key(x[0]), reverse=reverse)
        except: return
        
        for i, (_, k) in enumerate(data):
            try: self.tabela.move(k, "", i)
            except: continue
        self.tabela.heading(col, command=lambda c=col: self.ordenar_coluna(c, not reverse))

    def excluir_registros_selecionados(self):
        """Exclui permanentemente os registros selecionados."""
        selected_iids_str = self.tabela.selection() 
        if not selected_iids_str:
            ModernMessageBox.showwarning("Aviso", "Nenhum registro selecionado para excluir.")
            return
            
        try: record_ids = [int(iid) for iid in selected_iids_str]
        except ValueError: return

        count = len(record_ids)
        if not ModernMessageBox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir {count} item(ns)?"): return

        self.set_status(f"Excluindo {count} registros...")
        erros, sucessos = 0, 0

        for record_id in record_ids:
            try:
                if db.delete_registro(record_id): sucessos += 1
                else: erros += 1
            except: erros += 1

        self.atualizar_views() 
        if erros > 0: ModernMessageBox.showwarning("Aviso", f"{sucessos} excluídos.\nFalha ao excluir {erros} itens.")
        else: ModernMessageBox.showinfo("Sucesso", f"{sucessos} registros excluídos permanentemente.")

    def duplicar_registro(self):
        """Puxa os dados da linha para criar um novo lançamento baseado nela."""
        sel_list = self.tabela.selection()
        if not sel_list: 
            ModernMessageBox.showwarning("Aviso","Selecione um item para duplicar.")
            return
            
        record_id = int(sel_list[0])
        try:
            reg_series = self.df_registros.loc[record_id]
            self.clear_form() 
            self.entrada_data.set_date(datetime.now().date())
            self.parceiro_var.set(reg_series.get('Parceiro',''))
            self.res_var.set(reg_series.get('Residuo',''))
            self.destinacao_var.set(reg_series.get('Destinacao',''))
            self.entrada_pedido.delete(0, tk.END)
            self.entrada_pedido.insert(0, reg_series.get('PedidoCompra','')) 
            self.estado_var.set(reg_series.get('Estado','Sólido'))
            self.tipo_var.set(reg_series.get('Tipo','Venda'))
            modo = reg_series.get('Modo','kg')
            self.calc_mode_var.set(modo)
            
            vkg_db = reg_series.get('ValorPorKg',0.0) 
            vfechado_db = reg_series.get('ValorFechado',0.0) 
            
            self.root.after(50, lambda m=modo, vk=vkg_db, vf=vfechado_db: self.preencher_valor_residuo(m, vk, 0.0, vf))
            
            self.set_status("Registro duplicado. Insira peso e guarde.")
            self.nb.select(self.aba_cad_fundo) 
        except Exception as e: 
            ModernMessageBox.showerror("Erro", f"Erro ao duplicar: {e}")
            self.clear_form()

    def mostrar_menu_tabela(self, event):
        """Abre o menu de contexto (Botão direito)."""
        try:
            item = self.tabela.identify_row(event.y)
            if item:
                self.tabela.selection_set(item)
                self.tabela.focus(item)
                self.menu_tabela.post(event.x_root, event.y_root)
        except: pass

    def abrir_anexo_selecionado(self):
        """Abre o PDF/Imagem do MTR anexado."""
        sel = self.tabela.focus()
        if not sel: return
        try:
            rec_id = int(sel)
            caminho = self.df_registros.loc[rec_id, 'CaminhoAnexo']
            if not caminho or not os.path.exists(caminho):
                ModernMessageBox.showinfo("Anexo", "Este registro não possui anexo válido.")
                return
            os.startfile(os.path.abspath(caminho))
        except Exception as e:
            ModernMessageBox.showerror("Erro", f"Erro ao abrir arquivo: {e}")

    def marcar_certificados_ok(self):
        selected_iids_str = self.tabela.selection()
        if not selected_iids_str:
            ModernMessageBox.showwarning("Aviso", "Selecione os itens na tabela primeiro.")
            return
        ids = [int(i) for i in selected_iids_str]
        if not ModernMessageBox.askyesno("Confirmar", f"Marcar 'Certificado OK' = 'Sim' para {len(ids)} item(ns)?"): return
        sucessos = 0
        for rid in ids:
            try:
                if db.update_certificado(rid, "Sim") is not False: sucessos += 1
            except: pass
        self.atualizar_views()
        if sucessos > 0: ModernMessageBox.showinfo("Sucesso", f"{sucessos} certificados marcados.")

    def marcar_nf_ok(self):
        selected_iids_str = self.tabela.selection()
        if not selected_iids_str:
            ModernMessageBox.showwarning("Aviso", "Selecione os itens na tabela primeiro.")
            return
        ids = [int(i) for i in selected_iids_str]
        if not ModernMessageBox.askyesno("Confirmar", f"Marcar 'NF OK' = 'Sim' para {len(ids)} item(ns)?"): return
        sucessos = 0
        for rid in ids:
            try:
                if hasattr(db, 'update_nf'):
                    if db.update_nf(rid, "Sim") is not False: sucessos += 1
            except: pass
        self.atualizar_views()
        if sucessos > 0: ModernMessageBox.showinfo("Sucesso", f"{sucessos} Notas Fiscais marcadas.")

    def alterar_exigencias_lote(self):
        selecionados = self.tabela.selection()
        if not selecionados:
            ModernMessageBox.showwarning("Aviso", "Selecione pelo menos um registro na tabela.")
            return

        janela_lote = tb.Toplevel(self.root)
        janela_lote.title(f"Compliance em Lote ({len(selecionados)} itens)")
        janela_lote.geometry("350x200")
        janela_lote.resizable(False, False)
        janela_lote.transient(self.root); janela_lote.grab_set()

        tb.Label(janela_lote, text="Compliance:", font=("Segoe UI", 12, "bold"), bootstyle="secondary").pack(pady=(20, 10))

        frame_toggles = tb.Frame(janela_lote); frame_toggles.pack(pady=10)
        var_nf = tk.IntVar(value=1); var_cert = tk.IntVar(value=1)
        tb.Checkbutton(frame_toggles, text="Exige NF", variable=var_nf, bootstyle="round-toggle").pack(side="left", padx=15)
        tb.Checkbutton(frame_toggles, text="Exige Certificado", variable=var_cert, bootstyle="round-toggle").pack(side="left", padx=15)

        def salvar():
            sucessos = 0
            for iid in selecionados:
                try:
                    rid = int(iid)
                    row = self.df_registros.loc[rid]
                    val_cert_atual = str(row.get('CertificadoOK', '')).lower()
                    val_nf_atual = str(row.get('NFOk', '')).lower()
                    
                    cert_status = "Sim" if (var_cert.get() == 1 and val_cert_atual in ('sim', 'ok')) else ("Não" if var_cert.get() == 1 else "N/A")
                    nf_status = "Sim" if (var_nf.get() == 1 and val_nf_atual in ('sim', 'ok')) else ("Não" if var_nf.get() == 1 else "N/A")

                    db.update_certificado(rid, cert_status)
                    if hasattr(db, 'update_nf'): db.update_nf(rid, nf_status)
                    sucessos += 1
                except: pass

            janela_lote.destroy()
            self.atualizar_views()
            ModernMessageBox.showinfo("Sucesso", f"Regras aplicadas em {sucessos} registro(s)!")

        frame_btns = tb.Frame(janela_lote); frame_btns.pack(pady=15)
        tb.Button(frame_btns, text="Cancelar", bootstyle="secondary", command=janela_lote.destroy).pack(side="left", padx=10)
        tb.Button(frame_btns, text="Aplicar", bootstyle="success", command=salvar).pack(side="left")

    def marcar_pendencia_ok(self, event=None):
        """Marca como OK direto na aba de Pendências."""
        sel = self.pend_tbl.focus()
        if not sel: return
        try: record_id = int(sel)
        except ValueError: return
        try:
            reg_series = self.df_registros.loc[record_id]
            parceiro = reg_series['Parceiro']; residuo = reg_series['Residuo']
            data_dt = reg_series['Data']
            data_str_fmt = data_dt.strftime("%d/%m/%y") if pd.notna(data_dt) else "Sem data"
            
            if ModernMessageBox.askyesno("Confirmar", f"Marcar 'Sim'?\n({data_str_fmt} | {parceiro} | {residuo})?"):
                db.update_certificado(record_id, "Sim")
                self.atualizar_views()
                self.set_status("Certificado marcado como 'Sim'.")
        except Exception as e:
            ModernMessageBox.showerror("Erro", f"Erro ao atualizar pendência: {e}")

    def gerar_solicitacao_nf(self):
        """Reaproveita o módulo exportacao.py para gerar a NF"""
        selected_iids_str = self.tabela.selection()
        if not selected_iids_str:
            ModernMessageBox.showwarning("Seleção Vazia", "Nenhum registro selecionado.")
            return
        try:
            record_ids = [int(iid) for iid in selected_iids_str]
            template_path = self.get_resource_path('template_nf.xlsx')
            exportacao.gerar_solicitacao_nf_excel(
                self.root, record_ids, self.df_registros, self.banco_dict, 
                template_path, self.set_status, self.atualizar_views
            )
        except Exception as e:
            ModernMessageBox.showerror("Erro", f"Erro na solicitação de NF: {e}")

    # ==============================================================================
    # MÉTODOS DE EDIÇÃO (TABELA PRINCIPAL)
    # ==============================================================================
    def iniciar_edicao(self):
        """Puxa os dados da linha para o formulário para edição."""
        sel_list = self.tabela.selection()
        if not sel_list: 
            ModernMessageBox.showwarning("Aviso", "Selecione um registro na tabela para editar.")
            return
        
        record_id = int(sel_list[0])
        try:
            reg_series = self.df_registros.loc[record_id]
            self.editing_id = record_id 
            
            residuo_val = clean_str(reg_series.get('Residuo',''))
            
            # Lógica de roteamento: Análise, Frete ou Resíduo
            if residuo_val.startswith("[ANÁLISE]"):
                self.launch_type_var.set("Análise") 
                data_dt = reg_series.get('Data', pd.NaT)
                if pd.notna(data_dt): self.ana_data.set_date(data_dt.date())
                self.ana_parc_var.set(reg_series.get('Parceiro',''))
                nome_real = residuo_val.replace("[ANÁLISE] ", "").strip()
                self.ana_nome_var.set(nome_real)
                
                v_fechado = reg_series.get('ValorFechado', 0.0)
                self.ana_valor_fechado.delete(0, tk.END)
                self.ana_valor_fechado.insert(0, f"{v_fechado:.2f}".replace(".", ","))
                self.ana_pedido.delete(0, tk.END)
                self.ana_pedido.insert(0, reg_series.get('PedidoCompra',''))
                
                if hasattr(self, 'btn_ana_add'):
                    self.btn_ana_add.configure(text="Salvar Edição da Análise", bootstyle=WARNING)
                    self.btn_ana_add.editing_id = record_id 
                self.nb.select(self.aba_cad_fundo)
                
            elif residuo_val.startswith("[FRETE]"):
                self.launch_type_var.set("Transporte")
                data_dt = reg_series.get('Data', pd.NaT)
                if pd.notna(data_dt): self.transp_data.set_date(data_dt.date())
                self.transp_parc_var.set(reg_series.get('Parceiro',''))
                self.transp_res_var.set(residuo_val.replace("[FRETE] ", "").strip())
                v_total = reg_series.get('ValorTotal', 0.0)
                
                self.transp_valor.delete(0, tk.END)
                self.transp_valor.insert(0, f"{v_total:.2f}".replace(".", ","))
                self.transp_pedido.delete(0, tk.END)
                self.transp_pedido.insert(0, reg_series.get('PedidoCompra',''))
                self.nb.select(self.aba_cad_fundo)

            else:
                self.launch_type_var.set("Resíduo")
                self.clear_form()
                self.editing_id = record_id 
                
                data_dt = reg_series.get('Data', pd.NaT)
                if pd.notna(data_dt): self.entrada_data.set_date(data_dt.date())
                else: self.entrada_data.set_date(datetime.now().date())
                
                self.parceiro_var.set(reg_series.get('Parceiro',''))
                self.res_var.set(residuo_val)
                self.destinacao_var.set(reg_series.get('Destinacao',''))
                self.estado_var.set(reg_series.get('Estado','Sólido'))
                self.tipo_var.set(reg_series.get('Tipo','Venda'))
                
                modo = reg_series.get('Modo','kg')
                self.calc_mode_var.set(modo)
                
                val_nf = str(reg_series.get('NFOk', '')).upper()
                if val_nf in ['N/A', 'NA', 'DISPENSADO']: self.var_nf_manual.set(0)
                else: self.var_nf_manual.set(1) 
                
                val_cert = str(reg_series.get('CertificadoOK', '')).upper()
                if val_cert in ['N/A', 'NA', 'DISPENSADO']: self.var_cert_manual.set(0)
                else: self.var_cert_manual.set(1)
                
                self.entrada_pedido.delete(0, tk.END)
                self.entrada_pedido.insert(0, reg_series.get('PedidoCompra',''))
                
                peso_db_kg = reg_series.get('Peso', 0.0)
                vkg_db = reg_series.get('ValorPorKg', 0.0)
                vfechado_db = reg_series.get('ValorFechado', 0.0)
                transp = reg_series.get('Transporte', 0.0)
                
                # Aguarda a interface desenhar as caixas antes de injetar valores
                self.root.after(200, lambda m=modo, vk=vkg_db, ps=peso_db_kg, vf=vfechado_db, tr=transp: self.preencher_valores_edicao(m, vk, ps, vf, tr))
                
                self.btn_submit.configure(text="Salvar Edição", bootstyle=SUCCESS)
                self.btn_clear_form.configure(text="Cancelar Edição", bootstyle=WARNING)
                self.nb.select(self.aba_cad_fundo)

        except Exception as e: 
            ModernMessageBox.showerror("Erro", f"Erro ao carregar: {e}")
            self.clear_form()
            self.clear_form_analise()

    def preencher_valores_edicao(self, modo, vkg_db, peso_db_kg, vfechado_db, transp):
        """Função auxiliar para preencher os valores injetados no modo de edição."""
        self.peso_var.set(f"{Decimal(str(peso_db_kg)):.3f}".replace(".",",").rstrip("0").rstrip(","))

        visivel_kg = bool(self.entrada_valor_kg.grid_info())
        visivel_fec = bool(self.entrada_valor_fechado.grid_info())

        if modo in ("kg", "unidade"):
            self.entrada_valor_kg.delete(0, tk.END) 
            if visivel_kg:
                self.entrada_valor_kg.insert(0, f"{Decimal(str(vkg_db)):.3f}".replace(".", ",").rstrip("0").rstrip(","))
        elif modo == "fechado":
            self.entrada_valor_fechado.delete(0, tk.END) 
            if visivel_fec:
                self.entrada_valor_fechado.insert(0, f"{vfechado_db:.2f}".replace(".",","))

        self.entrada_transporte.delete(0, tk.END)
        self.entrada_transporte.insert(0, f"{transp:.2f}".replace(".",","))
        self.calcular_resumo_financeiro_automatico()

    # ==============================================================================
    # ESQUELETOS (STUBS) PARA AS ABAS ABRIREM SEM ERROS DE ATRIBUTOS
    # ==============================================================================
    
    # --- Funções da Aba Relatórios ---
    # ==============================================================================
    # MÉTODOS DA ABA DE ANÁLISE E DASHBOARD
    # ==============================================================================
    def aplicar_filtro_rapido_ana(self, periodo):
        hoje = date.today()
        if periodo == "mes": ini = hoje.replace(day=1); fim = hoje
        elif periodo == "ano": ini = hoje.replace(day=1, month=1); fim = hoje
        elif periodo == "tudo": ini = date(2020, 1, 1); fim = hoje
        elif periodo == "mes_passado":
            ultimo_mes_passado = hoje.replace(day=1) - timedelta(days=1)
            ini = ultimo_mes_passado.replace(day=1); fim = ultimo_mes_passado
            
        self.ana_data_inicio.set_date(ini)
        self.ana_data_fim.set_date(fim)
        self.atualizar_dashboard()

    def atualizar_dashboard(self):
        """Atualiza todos os gráficos e KPIs da aba Análise utilizando graficos.py."""
        try:
            dt_inicio = self.ana_data_inicio.get_date()
            dt_fim = self.ana_data_fim.get_date()
        except Exception as e: 
            ModernMessageBox.showerror("Erro Data", f"Formato inválido: {e}")
            return
            
        if dt_inicio > dt_fim: 
            ModernMessageBox.showwarning("Filtro Inválido", "Data início > Data fim.")
            return
        
        df_periodo = self.df_registros.copy()
        if not df_periodo.empty and 'Data' in df_periodo.columns:
            df_periodo['Data'] = pd.to_datetime(df_periodo['Data'], errors='coerce')
            mask = (df_periodo['Data'] >= pd.to_datetime(dt_inicio)) & (df_periodo['Data'] <= pd.to_datetime(dt_fim))
            df_periodo = df_periodo.loc[mask]
        else:
            df_periodo = pd.DataFrame()

        # Dicionário de cores dinâmicas para os gráficos baseado no tema
        cores = {
            'bg': self.style.colors.bg,
            'fg': self.style.colors.fg,
            'grid': self.style.colors.secondary,
            'info': self.style.colors.info,
            'danger': self.style.colors.danger,
            'success': self.style.colors.success
        }

        # Atualiza Totais e KPIs
        self.atualizar_totais(df_periodo)

        # Chamada do motor de gráficos modularizado
        import graficos
        graficos.atualizar_grafico_barras(df_periodo, self.ax_bar, self.canvas_bar, self.fig_bar, cores)
        graficos.atualizar_grafico_pie_custo(df_periodo, self.ax_pie_custo, self.canvas_pie_custo, self.fig_pie_custo, cores)
        graficos.atualizar_grafico_pie_peso(df_periodo, self.ax_pie_peso, self.canvas_pie_peso, self.fig_pie_peso, cores)
        graficos.atualizar_grafico_lucro_residuo(df_periodo, self.ax_lucro_res, self.canvas_lucro_res, self.fig_lucro_res, cores)
        graficos.atualizar_grafico_evolucao(self.df_registros, self.ax_evol, self.canvas_evol, self.fig_evol, cores)
        
        if hasattr(self, 'ax_estado_fin'):
            graficos.atualizar_grafico_estado_financeiro(df_periodo, self.ax_estado_fin, self.canvas_estado_fin, self.fig_estado_fin, cores)

        self.preencher_resumo(df_periodo)
        self.set_status(f"Análise atualizada: {dt_inicio:%d/%m/%y} - {dt_fim:%d/%m/%y}.")

    def atualizar_totais(self, df):
        """Calcula os cards superiores de Vendas, Custos e Lucro."""
        if df.empty:
            self.kpi_vendas_var.set("R$ 0,00")
            self.kpi_custos_var.set("R$ 0,00")
            self.kpi_lucro_var.set("R$ 0,00")
            self.kpi_peso_var.set("0 kg")
            return

        total_venda = df[df['Tipo'].str.lower() == 'venda']['ValorTotal'].sum() if 'ValorTotal' in df.columns else 0.0
        total_custo = df[df['Tipo'].str.lower() == 'custo']['ValorTotal'].sum() if 'ValorTotal' in df.columns else 0.0
        lucro = total_venda - total_custo
        
        col_peso = 'PesoEmKg' if 'PesoEmKg' in df.columns else 'Peso'
        total_peso = df[col_peso].sum() if col_peso in df.columns else 0.0

        self.kpi_vendas_var.set(fmt_moeda(total_venda))
        self.kpi_custos_var.set(fmt_moeda(total_custo))
        self.kpi_lucro_var.set(fmt_moeda(lucro))
        self.kpi_peso_var.set(fmt_kg(total_peso))

    def preencher_resumo(self, df):
        """Preenche a tabela de resumo mensal na aba Análise."""
        for r in self.resumo_tbl.get_children(): 
            self.resumo_tbl.delete(r)
        
        try:
            if df is None or df.empty: return
            rdf_raw, rdf_fmt = calculos.resumo_mensal_df(df)
            if rdf_raw is None or rdf_raw.empty: return

            expected_cols = self.resumo_cols
            row_num = 0
            raw_cols = [str(c) for c in rdf_raw.columns]
            col_lucro = next((c for c in raw_cols if 'lucro' in c.lower()), None)

            for idx in rdf_raw.index:
                row_fmt = rdf_fmt.loc[idx]
                values_tuple = [row_fmt.get(c, "") for c in expected_cols]
                
                lucro_val = 0
                if col_lucro:
                    try: lucro_val = float(rdf_raw.loc[idx, col_lucro])
                    except: pass
                
                tags = ["evenrow" if row_num % 2 == 0 else "oddrow"]
                if lucro_val < 0: tags.append("lucro_neg")
                elif lucro_val > 0: tags.append("lucro_pos")
                
                self.resumo_tbl.insert("", "end", iid=str(idx), values=tuple(values_tuple), tags=tuple(tags))
                row_num += 1
        except Exception as e:
            print(f"Erro ao preencher resumo: {e}")

    def mostrar_detalhes_resumo(self, event=None):
        sel = self.resumo_tbl.focus()
        if not sel: return
        try:
            item = self.resumo_tbl.item(sel)
            vals = item['values']
            mes_str, estado, destinacao = vals[0], vals[1], vals[2]
            
            df_detalhe = self.df_registros.copy()
            df_detalhe['Data'] = pd.to_datetime(df_detalhe['Data'], errors='coerce')
            mask = (df_detalhe['Estado'] == estado) & (df_detalhe['Destinacao'] == destinacao)
            df_detalhe = df_detalhe[mask]
            
            df_detalhe['Mes_Fmt'] = df_detalhe['Data'].apply(lambda x: f"{PT_ABREV_LIST[x.month-1]}/{x.year%100:02d}" if pd.notna(x) else "")
            df_detalhe = df_detalhe[df_detalhe['Mes_Fmt'] == mes_str]

            if df_detalhe.empty:
                ModernMessageBox.showinfo("Detalhes", "Nenhum registro individual encontrado.")
                return

            top = tb.Toplevel(self.root)
            top.title(f"Detalhes: {destinacao} ({mes_str})")
            top.geometry("700x400")
            tb.Label(top, text=f"Composição de: {estado} - {destinacao}", font=("Segoe UI", 12, "bold"), bootstyle="primary").pack(pady=10)
            
            cols = ("Data", "Parceiro", "Resíduo", "Peso", "Valor Total")
            tree_det = ttk.Treeview(top, columns=cols, show="headings")
            for c in cols: tree_det.heading(c, text=c); tree_det.column(c, anchor="center")
            tree_det.pack(fill="both", expand=True, padx=10, pady=5)
            
            for _, row in df_detalhe.iterrows():
                d_fmt = format_data_ptbr_abbrev([row['Data']])[0]
                peso_real = row['PesoEmKg'] if str(row.get('Modo')).lower() == 'unidade' else row['Peso']
                tree_det.insert("", "end", values=(d_fmt, clean_str(row['Parceiro']), clean_str(row['Residuo']), fmt_kg(peso_real), fmt_moeda(row['ValorTotal'])))
        except Exception as e:
            ModernMessageBox.showerror("Erro", f"Erro ao abrir detalhes: {e}")
    # ==============================================================================
    # MÉTODOS DOS RELATÓRIOS AVANÇADOS (ESG, BALANÇA, GERAÇÃO E ECOEFICIÊNCIA)
    # ==============================================================================
    
    # --- 1. INDICADORES ESG ---
    def desenhar_grafico_rosca(self, df_agrupado):
        if not hasattr(self, 'ax_esg_rosca'): return
        self.ax_esg_rosca.clear()
        bg_color, fg_color = self.style.colors.bg, self.style.colors.fg
        self.ax_esg_rosca.set_facecolor(bg_color)
        self.fig_esg_rosca.set_facecolor(bg_color)

        if df_agrupado.empty:
            self.ax_esg_rosca.text(0.5, 0.5, "Sem dados no período", ha='center', va='center', color=fg_color)
            self.canvas_esg_rosca.draw()
            return

        labels = df_agrupado['Destinacao'].tolist()
        valores = df_agrupado['Peso_KG_Real'].tolist()
        total_peso = sum(valores)

        palavras_verdes = ['reciclagem', 'compostagem', 'reuso', 'coprocessamento', 'co-processamento', 'recuperação', 'logística reversa']
        cores_finais = []
        paleta_neutra = ['#3498db', '#9b59b6', '#e67e22', '#f1c40f', '#e74c3c', '#95a5a6']
        idx_neutro = 0

        for dest in labels:
            d_lower = str(dest).lower()
            if 'efluente' in d_lower or 'aterro' in d_lower or 'incineração' in d_lower:
                cores_finais.append(paleta_neutra[idx_neutro % len(paleta_neutra)]); idx_neutro += 1
            elif any(pv in d_lower for pv in palavras_verdes):
                cores_finais.append('#2ecc71')
            else:
                cores_finais.append(paleta_neutra[idx_neutro % len(paleta_neutra)]); idx_neutro += 1

        wedges, texts, autotexts = self.ax_esg_rosca.pie(
            valores, autopct=lambda p: f'{p:.1f}%' if p > 3 else '', startangle=140,
            colors=cores_finais, textprops={'color': fg_color, 'fontsize': 10, 'weight': 'bold'},
            wedgeprops=dict(width=0.4, edgecolor=bg_color, linewidth=2), pctdistance=0.80 
        )

        self.ax_esg_rosca.set_title("Distribuição por Destinação Final", color=fg_color, weight='bold', pad=10)
        legend_labels = [f"{n[:25]} | {v/total_peso*100:.1f}% ({v:,.2f} kg)".replace(',', 'X').replace('.', ',').replace('X', '.') for n, v in zip(labels, valores)]
        self.ax_esg_rosca.legend(wedges, legend_labels, title="Destinações", loc="center left", bbox_to_anchor=(1.05, 0.5), fontsize=9, frameon=False, labelcolor=fg_color)
        self.fig_esg_rosca.subplots_adjust(left=0.05, bottom=0.05, right=0.55, top=0.85)
        self.canvas_esg_rosca.draw()

    def start_esg_calculation(self):
        try:
            dt_inicio = obter_data_segura(self.esg_data_inicio)
            dt_fim = obter_data_segura(self.esg_data_fim)
        except: 
            ModernMessageBox.showwarning("Aviso", "Verifique as datas inseridas.")
            return

        self.ax_esg_rosca.clear(); self.canvas_esg_rosca.draw()
        self.btn_gerar_esg.config(state="disabled")

        def thread_esg():
            try:
                df = get_df_com_peso_real(self.df_registros.copy())
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                df_f = df[(df['Data'].dt.date >= dt_inicio) & (df['Data'].dt.date <= dt_fim)]
                df_f = df_f[~df_f['Destinacao'].str.contains('Análise externa', case=False, na=False)]
                df_f = df_f[~df_f['Destinacao'].isin(['N/A'])]

                peso_total = df_f['Peso_KG_Real'].sum() if 'Peso_KG_Real' in df_f.columns else 0.0
                if peso_total == 0:
                    self.root.after(0, lambda: self.lbl_esg_geracao.config(text="0,00 kg"))
                    self.root.after(0, lambda: self.lbl_esg_taxa.config(text="0,0%"))
                    self.root.after(0, lambda: self.desenhar_grafico_rosca(pd.DataFrame()))
                    self.root.after(0, lambda: self.btn_gerar_esg.config(state="normal"))
                    return

                agrupado = df_f.groupby('Destinacao')['Peso_KG_Real'].sum().reset_index()
                agrupado = agrupado[agrupado['Peso_KG_Real'] > 0].sort_values(by='Peso_KG_Real', ascending=False)
                
                palavras_verdes = ['reciclagem', 'compostagem', 'reuso', 'coprocessamento', 'co-processamento', 'recuperação', 'logística reversa']
                def verifica_circularidade(dest):
                    d = str(dest).lower()
                    if 'efluente' in d or 'aterro' in d or 'incineração' in d: return False
                    return any(pv in d for pv in palavras_verdes)

                mask_v = agrupado['Destinacao'].apply(verifica_circularidade)
                peso_circular = agrupado[mask_v]['Peso_KG_Real'].sum()
                taxa_circ = (peso_circular / peso_total) * 100 if peso_total > 0 else 0.0

                peso_str = f"{peso_total:,.2f} kg".replace(",", "X").replace(".", ",").replace("X", ".")
                self.root.after(0, lambda: self.lbl_esg_geracao.config(text=peso_str))
                self.root.after(0, lambda: self.lbl_esg_taxa.config(text=f"{taxa_circ:.1f}%"))
                self.root.after(0, lambda: self.desenhar_grafico_rosca(agrupado))
                self.root.after(0, lambda: self.btn_gerar_esg.config(state="normal"))
            except:
                self.root.after(0, lambda: self.btn_gerar_esg.config(state="normal"))

        threading.Thread(target=thread_esg, daemon=True).start()

    # --- 2. BALANÇA COMERCIAL ---
    def calcular_balanca_comercial(self):
        try:
            dt_inicio = obter_data_segura(self.fin_data_inicio)
            dt_fim = obter_data_segura(self.fin_data_fim)
        except:
            ModernMessageBox.showwarning("Aviso", "Verifique as datas inseridas.")
            return

        self.ax_fin.clear(); self.canvas_fin.draw()
        self.btn_gerar_fin.config(state="disabled")

        def thread_fin():
            try:
                df = self.df_registros.copy()
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
                df = df[(df['Data'].dt.date >= dt_inicio) & (df['Data'].dt.date <= dt_fim)]
                if df.empty or 'ValorTotal' not in df.columns:
                    self.root.after(0, lambda: self.btn_gerar_fin.config(state="normal"))
                    return

                palavras_receita = ['venda', 'sucata', 'venda de recicláveis', 'receita']
                df['Is_Receita'] = df['Destinacao'].apply(lambda d: any(pr in str(d).lower() for pr in palavras_receita))

                df['Mes_Ano'] = df['Data'].dt.to_period('M')
                df_grafico = df.groupby(['Mes_Ano', 'Is_Receita'])['ValorTotal'].sum().unstack(fill_value=0).reset_index()
                if True not in df_grafico.columns: df_grafico[True] = 0.0
                if false_col := [c for c in df_grafico.columns if c is False]: pass
                elif False not in df_grafico.columns: df_grafico[False] = 0.0

                df_grafico = df_grafico.sort_values('Mes_Ano')
                dados_metragem = db.get_all_metragens() 
                dict_metragem = {item[0]: item[1] for item in dados_metragem}

                linhas, x_labels, val_c, val_r = [], [], [], []
                rec_tot = cus_tot = met_tot = 0.0

                for _, row in df_grafico.iterrows():
                    m_p = row['Mes_Ano']
                    chave_db = f"{m_p.year}-{m_p.month:02d}"
                    met = dict_metragem.get(chave_db, 0.0)
                    rec = float(row.get(True, 0.0))
                    cus = float(row.get(False, 0.0))
                    creal = cus - rec
                    ind = (creal / met) if met > 0 else 0.0
                    mes_str = f"{PT_ABREV_LIST[m_p.month-1].capitalize()}/{m_p.year%100:02d}"
                    
                    linhas.append((mes_str, rec, cus, creal, met, ind))
                    rec_tot += rec; cus_tot += cus; met_tot += met
                    x_labels.append(mes_str); val_c.append(cus); val_r.append(rec)

                saldo_real = cus_tot - rec_tot
                kpi_tot = saldo_real / met_tot if met_tot > 0 else 0.0

                self.root.after(0, lambda: self.atualizar_ui_fin(linhas, rec_tot, cus_tot, kpi_tot, x_labels, val_c, val_r))
            except Exception as e:
                print(f"Erro Fin: {e}")
                self.root.after(0, lambda: self.btn_gerar_fin.config(state="normal"))

        threading.Thread(target=thread_fin, daemon=True).start()

    def atualizar_ui_fin(self, linhas, rec_tot, cus_tot, kpi_tot, x_labels, val_custos, val_receitas):
        self.lbl_fin_receita.config(text=fmt_moeda(rec_tot))
        self.lbl_fin_custo.config(text=fmt_moeda(cus_tot))
        self.lbl_fin_kpi.config(text=f"R$ {kpi_tot:,.2f} / m²".replace(",", "X").replace(".", ",").replace("X", "."))

        for r in self.fin_tbl.get_children(): self.fin_tbl.delete(r)
        for i, (mes, rec, cus, creal, met, ind) in enumerate(linhas):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.fin_tbl.insert("", "end", values=(mes, fmt_moeda(rec), fmt_moeda(cus), fmt_moeda(creal), f"{met:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), f"{ind:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")), tags=(tag,))

        self.ax_fin.clear()
        bg_color, fg_color = self.style.colors.bg, self.style.colors.fg
        self.ax_fin.set_facecolor(bg_color); self.fig_fin.set_facecolor(bg_color)
        x = np.arange(len(x_labels)); width = 0.35
        self.ax_fin.bar(x - width/2, val_custos, width, label='Custos', color='#e74c3c')
        self.ax_fin.bar(x + width/2, val_receitas, width, label='Receitas', color='#2ecc71')
        self.ax_fin.set_title("Balança Comercial Mensal (R$)", color=fg_color, weight='bold', fontsize=10)
        self.ax_fin.set_xticks(x); self.ax_fin.set_xticklabels(x_labels, rotation=30, ha='right', color=fg_color, fontsize=8)
        self.ax_fin.tick_params(axis='y', colors=fg_color, labelsize=8)
        self.ax_fin.yaxis.grid(True, linestyle=':', color=self.style.colors.secondary, alpha=0.4)
        for spine in ['top', 'right']: self.ax_fin.spines[spine].set_visible(False)
        self.ax_fin.legend(loc='upper left', frameon=False, labelcolor=fg_color, fontsize=8)
        self.fig_fin.subplots_adjust(bottom=0.2)
        self.canvas_fin.draw()
        self.btn_gerar_fin.config(state="normal")

    # --- 3. GERAÇÃO (RATEIO) ---
    def start_geracao_calculation(self):
        try:
            dt_inicio = obter_data_segura(self.ger_data_inicio)
            dt_fim = obter_data_segura(self.ger_data_fim)
        except: return

        selecao = clean_str(self.ger_res_var.get())
        if not selecao: return

        for r in self.ger_tbl.get_children(): self.ger_tbl.delete(r)
        self.ger_kpi_total_var.set("Calculando...")
        self.ger_kpi_media_var.set("Calculando...")
        self.btn_gerar_geracao.config(state="disabled")

        df_copy = get_df_com_peso_real(self.df_registros.copy())
        if not self.df_banco.empty and 'Grupo' in self.df_banco.columns:
            residuos_alvo = self.df_banco[self.df_banco['Grupo'] == selecao]['Residuo'].tolist()
            if not residuos_alvo: residuos_alvo = [selecao]
        else: residuos_alvo = [selecao]

        def thread_geracao():
            try:
                res = calculos.calcular_relatorio_geracao_data(dt_inicio, dt_fim, residuos_alvo, df_copy)
                self.root.after(0, lambda: self.atualizar_ui_geracao(res))
            except Exception as e:
                self.root.after(0, lambda: ModernMessageBox.showerror("Erro", f"Erro no cálculo: {e}"))
                self.root.after(0, lambda: self.btn_gerar_geracao.config(state="normal"))

        threading.Thread(target=thread_geracao, daemon=True).start()

    def atualizar_ui_geracao(self, result_data):
        for r in self.ger_tbl.get_children(): self.ger_tbl.delete(r)
        self.txt_memoria_geracao.delete("1.0", tk.END)
        if "memoria" in result_data: self.txt_memoria_geracao.insert(tk.END, result_data["memoria"])

        tot_f = f"{result_data['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        med_f = f"{result_data['media_diaria']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.ger_kpi_total_var.set(f"{tot_f} kg")
        self.ger_kpi_media_var.set(f"{med_f} kg/dia")

        for row_num, linha in enumerate(result_data["linhas"]):
            r_str = f"{linha['Realizado']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Realizado'] > 0 else "-"
            p_str = f"{linha['Previsao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Previsao'] > 0 else "-"
            t_str = f"{linha['Total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Total'] > 0 else "-"
            tag = "evenrow" if row_num % 2 == 0 else "oddrow"
            self.ger_tbl.insert("", "end", values=(linha['Mes'].capitalize(), r_str, p_str, t_str), tags=(tag,))
        
        self.btn_gerar_geracao.config(state="normal")

    # --- 4. ECOEFICIÊNCIA ---
    def calcular_ecoeficiencia(self):
        try:
            dt_inicio = obter_data_segura(self.eco_data_inicio)
            dt_fim = obter_data_segura(self.eco_data_fim)
        except: return

        selecao = clean_str(self.eco_res_var.get())
        if not selecao: 
            ModernMessageBox.showwarning("Aviso", "Selecione um resíduo ou grupo.")
            return

        for r in self.eco_tbl.get_children(): self.eco_tbl.delete(r)
        self.btn_gerar_eco.config(state="disabled")

        def thread_eco():
            try:
                df_copy = self.df_registros.copy()
                if not self.df_banco.empty and 'Grupo' in self.df_banco.columns:
                    residuos_alvo = self.df_banco[self.df_banco['Grupo'] == selecao]['Residuo'].tolist()
                    if not residuos_alvo: residuos_alvo = [selecao]
                else: residuos_alvo = [selecao]

                res_ger = calculos.calcular_relatorio_geracao_data(dt_inicio, dt_fim, residuos_alvo, df_copy)
                dict_metragem = {item[0]: item[1] for item in db.get_all_metragens()}

                linhas_finais, eixo_x, eixo_y = [], [], []
                mapa_meses = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06", "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"}

                for linha in res_ger.get("linhas", []):
                    mes_str = linha['Mes']
                    partes = mes_str.split('/')
                    ano = partes[1] if len(partes[1]) == 4 else f"20{partes[1]}"
                    chave_db = f"{ano}-{mapa_meses.get(partes[0].lower(), '01')}"
                    
                    met = dict_metragem.get(chave_db, 0.0)
                    ger = linha['Total']
                    ind = (ger / met) if met > 0 else 0.0
                    
                    linhas_finais.append((mes_str.capitalize(), ger, met, ind))
                    eixo_x.append(mes_str.capitalize()); eixo_y.append(ind)

                self.root.after(0, lambda: self.atualizar_ui_eco(linhas_finais, eixo_x, eixo_y))
            except Exception as e:
                self.root.after(0, lambda: self.btn_gerar_eco.config(state="normal"))

        threading.Thread(target=thread_eco, daemon=True).start()

    def atualizar_ui_eco(self, linhas, x, y):
        for r in self.eco_tbl.get_children(): self.eco_tbl.delete(r)
        for i, (mes, ger, met, ind) in enumerate(linhas):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.eco_tbl.insert("", "end", values=(mes, f"{ger:,.2f}".replace(',','X').replace('.',',').replace('X','.'), f"{met:,.2f}".replace(',','X').replace('.',',').replace('X','.'), f"{ind:,.2f}".replace(',','X').replace('.',',').replace('X','.')), tags=(tag,))
        
        self.ax_eco.clear()
        bg_color, fg_color = self.style.colors.bg, self.style.colors.fg
        self.ax_eco.set_facecolor(bg_color); self.fig_eco.set_facecolor(bg_color)
        
        if sum(y) == 0:
            self.ax_eco.set_title("Nenhum dado ou metragem zerada", color=fg_color, fontsize=10)
        else:
            self.ax_eco.plot(x, y, marker='o', color=self.style.colors.success, linewidth=2)
            self.ax_eco.set_title("Evolução (kg/m²)", color=fg_color, fontsize=10, weight='bold')
            self.ax_eco.yaxis.grid(True, linestyle=':', color=self.style.colors.secondary, alpha=0.4)
            self.ax_eco.tick_params(axis='x', colors=fg_color, labelsize=8, rotation=30)
            self.ax_eco.tick_params(axis='y', colors=fg_color, labelsize=8)
            for spine in ['top', 'right']: self.ax_eco.spines[spine].set_visible(False)
            for spine in ['left', 'bottom']: self.ax_eco.spines[spine].set_color(self.style.colors.secondary)
            for i, v in enumerate(y):
                if v > 0: self.ax_eco.text(i, v + (max(y)*0.05), f"{v:.2f}", color=fg_color, ha='center', fontsize=7)

        self.canvas_eco.draw()
        self.btn_gerar_eco.config(state="normal")

    def exportar_ecoeficiencia_excel(self):
        itens = self.eco_tbl.get_children()
        if not itens: ModernMessageBox.showwarning("Aviso", "Não há dados."); return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"Ecoeficiencia_{datetime.now():%d-%m-%Y}.xlsx", title="Salvar Excel")
        if not path: return
        df_export = pd.DataFrame([self.eco_tbl.item(item)['values'] for item in itens], columns=["Mês", "Geração (kg)", "Produção (m²)", "Indicador (kg/m²)"])
        try:
            df_export.to_excel(path, index=False)
            ModernMessageBox.showinfo("Sucesso", "Exportado com sucesso!")
        except Exception as e: ModernMessageBox.showerror("Erro", f"{e}")

    def exportar_ecoeficiencia_pdf(self):
        """Gera um PDF profissional com a tabela e o gráfico de Ecoeficiência."""
        itens = self.eco_tbl.get_children()
        if not itens:
            ModernMessageBox.showwarning("Aviso", "Gere o indicador na tela primeiro.")
            return

        residuo = self.eco_res_var.get()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"Relatorio_Ecoeficiencia_{residuo}.pdf",
            title="Salvar Relatório em PDF"
        )
        if not path: return

        def gerar_pdf_eco_pesado():
            try:
                # 1. Captura o Gráfico atual em alta resolução como imagem
                buf = io.BytesIO()
                self.fig_eco.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white')
                buf.seek(0)
                img_grafico = RLImage(buf, width=18*cm, height=10*cm)

                # 2. Configura o documento ReportLab
                doc = SimpleDocTemplate(path, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
                styles = getSampleStyleSheet()
                elements = []

                # Título e Informações
                elements.append(Paragraph(f"Relatório de Ecoeficiência - {residuo}", styles['Title']))
                
                try:
                    dt_ini_str = self.eco_data_inicio.get_date().strftime('%d/%m/%Y')
                    dt_fim_str = self.eco_data_fim.get_date().strftime('%d/%m/%Y')
                except:
                    dt_ini_str = ""
                    dt_fim_str = ""

                elements.append(Paragraph(f"Período: {dt_ini_str} a {dt_fim_str}", styles['Normal']))
                elements.append(Spacer(1, 0.5*cm))

                # Imagem do Gráfico
                elements.append(Paragraph("Evolução Mensal", styles['Heading2']))
                elements.append(img_grafico)
                elements.append(Spacer(1, 0.5*cm))

                # Tabela de Dados
                elements.append(Paragraph("Detalhamento dos Dados", styles['Heading2']))
                data_pdf = [["Mês", "Geração (kg)", "Produção (m²)", "Indicador"]]
                for item in itens:
                    data_pdf.append(self.eco_tbl.item(item)['values'])

                table = Table(data_pdf, colWidths=[4.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('TOPPADDING', (0, 0), (-1, 0), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#ECF0F1")]),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                ]))
                elements.append(table)

                doc.build(elements)
                self.root.after(0, lambda: ModernMessageBox.showinfo("Sucesso", "Relatório PDF gerado com sucesso!"))
            except Exception as e:
                self.root.after(0, lambda: ModernMessageBox.showerror("Erro PDF", f"Falha ao gerar PDF: {e}"))

        # Executa de forma assíncrona usando a função de carregamento existente em exportacao.py
        exportacao.executar_com_carregamento(self.root, gerar_pdf_eco_pesado, "Gerando PDF", "Desenhando documento de ecoeficiência...")

 # ==============================================================================
    # MÉTODOS DE CONFIGURAÇÃO E CRUD (RESÍDUOS, PARCEIROS E ANÁLISES)
    # ==============================================================================
    
    def banco_add(self):
        """Abre a janela de gerenciamento em 'Modo Adicionar Resíduo'."""
        self.abrir_janela_gerenciar_residuo(nome_antigo=None)

    def banco_edit_wrapper(self):
        """Pega o resíduo selecionado na tabela e abre para edição."""
        sel = self.bn_tbl.focus()
        idx = int(sel) if sel else -1
        if idx == -1: 
            ModernMessageBox.showerror("Erro", "Selecione um resíduo para editar.")
            return
        try:
            nome_antigo = self.df_banco.loc[idx, "Residuo"]
            self.abrir_janela_gerenciar_residuo(nome_antigo=nome_antigo)
        except (KeyError, IndexError): 
            ModernMessageBox.showerror("Erro", "Índice inválido ou dados não encontrados.")

    def banco_del(self):
        """Exclui o resíduo selecionado do banco."""
        sel = self.bn_tbl.focus()
        idx = int(sel) if sel else -1
        if idx == -1: ModernMessageBox.showerror("Erro", "Selecione um resíduo."); return
        try: nome = self.df_banco.loc[idx, "Residuo"]
        except (KeyError, IndexError): ModernMessageBox.showerror("Erro", "Índice inválido."); return
        
        if ModernMessageBox.askyesno("Confirmar", f"Excluir resíduo '{nome}'?"):
            if db.delete_residuo(nome): 
                self.atualizar_views()
                self.set_status("Resíduo excluído.")
            else: ModernMessageBox.showerror("Erro", "Falha ao excluir resíduo.")

    def banco_edit_grupo_lote(self):
        """Abre pop-up para aplicar o mesmo Grupo de Relatório a vários resíduos."""
        selecionados = self.bn_tbl.selection()
        if not selecionados:
            ModernMessageBox.showwarning("Aviso", "Selecione pelo menos um resíduo na tabela.")
            return

        janela_lote = tb.Toplevel(self.root)
        janela_lote.title("Agrupar em Lote")
        janela_lote.geometry("450x220")
        janela_lote.resizable(False, False)
        janela_lote.transient(self.root); janela_lote.grab_set()

        tb.Label(janela_lote, text=f"Definir 'Grupo' para {len(selecionados)} resíduo(s):", font=("Segoe UI", 11, "bold")).pack(pady=(20, 10))

        grupos_relatorio = sorted(["Bombonas", "Plásticos", "Mylar", "Alumínio", "Papel", "Sucata de ferro", "Fresa sem ouro", "Fresa com ouro", "Placa com ouro", "Placa sem ouro", "Cobre", "Madeira", "Filme fotossensível", "Borra de tinta", "Lodo", "Sólidos contaminados", "Concentrado", "Solução amoniacal", "Solução ácida contendo cobre", "Solução ácida contendo estanho"])
        grupo_lote_var = tk.StringVar()
        cb_grupo = tb.Combobox(janela_lote, textvariable=grupo_lote_var, values=grupos_relatorio, state="normal")
        cb_grupo.pack(fill="x", padx=40, pady=10)

        def salvar_lote():
            novo_grupo = clean_str(grupo_lote_var.get())
            sucessos = 0
            for iid in selecionados:
                idx = int(iid)
                try:
                    nome_atual = self.df_banco.loc[idx, "Residuo"]
                    dados = self.banco_dict.get(nome_atual, {})
                    if db.update_residuo(
                        nome_atual, nome_atual, dados.get('nome_nf', ''), dados.get('codigo_item', ''),
                        dados.get('codigo_ibama', ''), dados.get('modo', 'kg'), float(dados.get('kg', 0.0)),
                        float(dados.get('fechado', 0.0)), float(dados.get('peso_unitario', 0.0)),
                        int(dados.get('calcula_rateio', 0)), dados.get('estado_padrao', ''),
                        dados.get('destinacao_padrao', ''), dados.get('tipo_padrao', ''),
                        dados.get('parceiro_padrao', ''), novo_grupo, int(dados.get('exige_nf', 1)),
                        int(dados.get('exige_cert', 1))
                    ): sucessos += 1
                except: pass

            janela_lote.destroy()
            if sucessos > 0:
                self.atualizar_views()
                ModernMessageBox.showinfo("Sucesso", f"Grupo aplicado em {sucessos} resíduo(s)!")

        frame_btns = tb.Frame(janela_lote); frame_btns.pack(pady=15)
        tb.Button(frame_btns, text="Cancelar", command=janela_lote.destroy, bootstyle=SECONDARY).pack(side="left", padx=10)
        tb.Button(frame_btns, text="Aplicar Grupo", bootstyle=SUCCESS, command=salvar_lote).pack(side="left")

    def reclassificar_lote(self):
        """Renomeia um resíduo em massa em todas as tabelas."""
        sel = self.bn_tbl.focus()
        if not sel: return
        try: nome_antigo = self.df_banco.loc[int(sel), "Residuo"]
        except: return
        
        novo_nome = simpledialog.askstring("Reclassificar", f"Novo nome para '{nome_antigo}':", parent=self.root)
        if novo_nome and novo_nome != nome_antigo:
            if db.renomear_residuo_em_massa(nome_antigo, novo_nome):
                ModernMessageBox.showinfo("Sucesso", "Resíduo renomeado com sucesso!")
                self.atualizar_views()
            else:
                ModernMessageBox.showerror("Erro", "Falha ao renomear resíduo.")

    def parceiros_add(self):
        self.abrir_janela_gerenciar_parceiro(nome_antigo=None)

    def parceiros_edit_wrapper(self):
        sel = self.pc_tbl.focus()
        idx = int(sel) if sel else -1
        if idx == -1: 
            ModernMessageBox.showerror("Erro", "Selecione um parceiro para editar.")
            return
        try:
            nome_antigo = self.df_parceiros.loc[idx, "Parceiro"]
            self.abrir_janela_gerenciar_parceiro(nome_antigo=nome_antigo)
        except: 
            ModernMessageBox.showerror("Erro", "Erro ao carregar parceiro.")

    def parceiros_del(self):
        sel = self.pc_tbl.focus()
        idx = int(sel) if sel else -1
        if idx == -1: ModernMessageBox.showerror("Erro", "Selecione um parceiro."); return
        try: nome = self.df_parceiros.loc[idx, "Parceiro"]
        except: return
        
        if ModernMessageBox.askyesno("Confirmar", f"Excluir parceiro '{nome}'?"):
            if db.delete_parceiro(nome): 
                self.atualizar_views()
                self.set_status("Parceiro excluído.")
            else: ModernMessageBox.showerror("Erro", "Falha ao excluir.")

    def analises_add(self):
        self.abrir_janela_gerenciar_analise(nome_antigo=None)

    def analises_edit_wrapper(self):
        sel = self.bana_tbl.focus()
        idx = int(sel) if sel else -1
        if idx == -1: 
            ModernMessageBox.showerror("Erro", "Selecione uma análise para editar.")
            return
        try:
            nome_antigo = self.df_analises.loc[idx, "NomeAnalise"]
            self.abrir_janela_gerenciar_analise(nome_antigo=nome_antigo)
        except: 
            ModernMessageBox.showerror("Erro", "Erro ao carregar análise.")

    def analises_del(self):
        sel = self.bana_tbl.focus()
        idx = int(sel) if sel else -1
        if idx == -1: ModernMessageBox.showerror("Erro", "Selecione uma análise."); return
        try: nome = self.df_analises.loc[idx, "NomeAnalise"]
        except: return
        
        if ModernMessageBox.askyesno("Confirmar", f"Excluir análise '{nome}'?"):
            if db.delete_analise(nome): 
                self.atualizar_views()
                self.set_status("Análise excluída.")
            else: ModernMessageBox.showerror("Erro", "Falha ao excluir.")

    # --- POP-UPS DE GERENCIAMENTO DE CADASTRO ---
    def abrir_janela_gerenciar_residuo(self, nome_antigo=None):
        is_edit_mode = (nome_antigo is not None)
        dados_atuais = self.banco_dict.get(nome_antigo, {}) if is_edit_mode else {}
        
        edit_window = tb.Toplevel(self.root)
        edit_window.title(f"Editar: {nome_antigo}" if is_edit_mode else "Novo Resíduo")
        edit_window.geometry("900x580"); edit_window.transient(self.root); edit_window.grab_set()
        
        main_frame = tb.Frame(edit_window, padding=15); main_frame.pack(fill="both", expand=True)
        col_esq = tb.Labelframe(main_frame, text="Dados Básicos & Valores", padding=10); col_esq.pack(side="left", fill="both", expand=True, padx=(0,10))
        col_dir = tb.Labelframe(main_frame, text="Auto-Preenchimento (Padrões)", padding=10, bootstyle=INFO); col_dir.pack(side="right", fill="both", expand=True)

        nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
        nome_nf_var = tk.StringVar(value=dados_atuais.get('nome_nf', ''))
        codigo_item_var = tk.StringVar(value=dados_atuais.get('codigo_item', ''))
        modo_var = tk.StringVar(value=dados_atuais.get('modo', 'kg'))
        val_kg_var = tk.StringVar(value=f"{dados_atuais.get('kg', 0.0):.3f}".replace('.',','))
        val_fec_var = tk.StringVar(value=f"{dados_atuais.get('fechado', 0.0):.2f}".replace('.',','))
        peso_unit_var = tk.StringVar(value=f"{dados_atuais.get('peso_unitario', 0.0):.3f}".replace('.',','))
        exige_nf_var = tk.IntVar(value=1 if not is_edit_mode else int(dados_atuais.get('exige_nf', 1)))
        exige_cert_var = tk.IntVar(value=1 if not is_edit_mode else int(dados_atuais.get('exige_cert', 1)))
        
        padrao_estado_var = tk.StringVar(value=dados_atuais.get('estado_padrao', ''))
        padrao_dest_var = tk.StringVar(value=dados_atuais.get('destinacao_padrao', ''))
        padrao_tipo_var = tk.StringVar(value=dados_atuais.get('tipo_padrao', ''))
        padrao_parc_var = tk.StringVar(value=dados_atuais.get('parceiro_padrao', ''))

        r=0
        tb.Label(col_esq, text="Resíduo (Interno):").grid(row=r, column=0, sticky="w", pady=5)
        tb.Entry(col_esq, textvariable=nome_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_esq, text="Nome p/ NF:").grid(row=r, column=0, sticky="w", pady=5)
        tb.Entry(col_esq, textvariable=nome_nf_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_esq, text="Código Item:").grid(row=r, column=0, sticky="w", pady=5)
        tb.Entry(col_esq, textvariable=codigo_item_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_esq, text="Modo de Cálculo:").grid(row=r, column=0, sticky="w", pady=5)
        tb.Combobox(col_esq, textvariable=modo_var, values=['kg', 'fechado', 'unidade'], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_esq, text="Valor/kg (R$):").grid(row=r, column=0, sticky="w", pady=5)
        tb.Entry(col_esq, textvariable=val_kg_var, validate="key", validatecommand=self.vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_esq, text="Valor Fechado (R$):").grid(row=r, column=0, sticky="w", pady=5)
        tb.Entry(col_esq, textvariable=val_fec_var, validate="key", validatecommand=self.vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_esq, text="Peso/Unidade (kg):").grid(row=r, column=0, sticky="w", pady=5)
        tb.Entry(col_esq, textvariable=peso_unit_var, validate="key", validatecommand=self.vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1

        r=0
        tb.Label(col_dir, text="Estado Padrão:").grid(row=r, column=0, sticky="w", pady=5)
        tb.Combobox(col_dir, textvariable=padrao_estado_var, values=["Sólido", "Líquido"], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_dir, text="Destinação Padrão:").grid(row=r, column=0, sticky="w", pady=5)
        tb.Combobox(col_dir, textvariable=padrao_dest_var, values=self.destinacoes, state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_dir, text="Tipo (Venda/Custo):").grid(row=r, column=0, sticky="w", pady=5)
        tb.Combobox(col_dir, textvariable=padrao_tipo_var, values=["Venda", "Custo"], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(col_dir, text="Parceiro Padrão:").grid(row=r, column=0, sticky="w", pady=5)
        tb.Combobox(col_dir, textvariable=padrao_parc_var, values=self.parceiros, state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Separator(col_dir, orient='horizontal').grid(row=r, column=0, columnspan=2, sticky="ew", pady=15); r+=1
        tb.Checkbutton(col_dir, text="Exige Nota Fiscal (NF)?", variable=exige_nf_var, bootstyle="round-toggle").grid(row=r, column=0, columnspan=2, sticky="w", pady=5); r+=1
        tb.Checkbutton(col_dir, text="Exige Certificado?", variable=exige_cert_var, bootstyle="round-toggle").grid(row=r, column=0, columnspan=2, sticky="w", pady=5); r+=1

        frame_btns = tb.Frame(edit_window); frame_btns.pack(fill="x", padx=15, pady=10)
        
        def salvar_dados_residuo():
            nome_novo = clean_str(nome_var.get())
            if not nome_novo: ModernMessageBox.showerror("Erro", "O nome não pode ser vazio.", parent=edit_window); return
            success = False
            if is_edit_mode:
                if db.update_residuo(nome_antigo, nome_novo, clean_str(nome_nf_var.get()), clean_str(codigo_item_var.get()), "", clean_str(modo_var.get()), to_float_safe(val_kg_var.get()), to_float_safe(val_fec_var.get()), to_float_safe(peso_unit_var.get()), 0, clean_str(padrao_estado_var.get()), clean_str(padrao_dest_var.get()), clean_str(padrao_tipo_var.get()), clean_str(padrao_parc_var.get()), "", exige_nf_var.get(), exige_cert_var.get()): success = True
            else:
                if db.add_residuo(nome_novo, clean_str(nome_nf_var.get()), clean_str(codigo_item_var.get()), "", clean_str(modo_var.get()), to_float_safe(val_kg_var.get()), to_float_safe(val_fec_var.get()), to_float_safe(peso_unit_var.get()), 0, clean_str(padrao_estado_var.get()), clean_str(padrao_dest_var.get()), clean_str(padrao_tipo_var.get()), clean_str(padrao_parc_var.get()), "", exige_nf_var.get(), exige_cert_var.get()): success = True

            if success:
                edit_window.destroy()
                self.atualizar_views()

        tb.Button(frame_btns, text="Cancelar", command=edit_window.destroy, bootstyle=SECONDARY).pack(side="right", padx=(10, 0))
        tb.Button(frame_btns, text="Salvar" if is_edit_mode else "Adicionar", command=salvar_dados_residuo, bootstyle=SUCCESS).pack(side="right")

    def abrir_janela_gerenciar_parceiro(self, nome_antigo=None):
        is_edit_mode = (nome_antigo is not None)
        tipo_atual = "Destinador"; cnpj_atual = ""
        if is_edit_mode:
            try:
                df_f = self.df_parceiros[self.df_parceiros['Parceiro'] == nome_antigo]
                tipo_atual = df_f['TipoParceiro'].iloc[0]
                if 'CNPJ' in self.df_parceiros.columns: cnpj_atual = df_f['CNPJ'].iloc[0]
            except: pass

        edit_window = tb.Toplevel(self.root)
        edit_window.title(f"Editar Parceiro: {nome_antigo}" if is_edit_mode else "Novo Parceiro")
        edit_window.geometry("450x230"); edit_window.resizable(False, False)
        edit_window.transient(self.root); edit_window.grab_set() 
        
        main_frame = tb.Frame(edit_window, padding=15); main_frame.pack(fill="both", expand=True); main_frame.columnconfigure(1, weight=1)
        nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
        tipo_var = tk.StringVar(value=tipo_atual)
        cnpj_var = tk.StringVar(value=cnpj_atual)

        r=0
        tb.Label(main_frame, text="Nome:").grid(row=r, column=0, sticky="w", pady=5); tb.Entry(main_frame, textvariable=nome_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(main_frame, text="CNPJ:").grid(row=r, column=0, sticky="w", pady=5); tb.Entry(main_frame, textvariable=cnpj_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(main_frame, text="Tipo:").grid(row=r, column=0, sticky="w", pady=5); tb.Combobox(main_frame, textvariable=tipo_var, values=["Destinador", "Laboratório", "Transportador"], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1

        def salvar():
            n_novo = clean_str(nome_var.get())
            if not n_novo: return
            if is_edit_mode: db.update_parceiro(nome_antigo, n_novo, tipo_var.get(), cnpj_var.get())
            else: db.add_parceiro(n_novo, tipo_var.get(), cnpj_var.get())
            edit_window.destroy(); self.atualizar_views()

        tb.Button(main_frame, text="Salvar", command=salvar, bootstyle=SUCCESS).pack(side="right", pady=15)

    def abrir_janela_gerenciar_analise(self, nome_antigo=None):
        is_edit_mode = (nome_antigo is not None)
        v_atual = self.analises_dict.get(nome_antigo, 0.0) if is_edit_mode else 0.0

        edit_window = tb.Toplevel(self.root)
        edit_window.title(f"Editar Análise: {nome_antigo}" if is_edit_mode else "Nova Análise")
        edit_window.geometry("450x200"); edit_window.transient(self.root); edit_window.grab_set()

        main_frame = tb.Frame(edit_window, padding=15); main_frame.pack(fill="both", expand=True); main_frame.columnconfigure(1, weight=1)
        nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
        valor_var = tk.StringVar(value=f"{v_atual:.2f}".replace(".", ","))

        r=0
        tb.Label(main_frame, text="Nome:").grid(row=r, column=0, sticky="w", pady=5); tb.Entry(main_frame, textvariable=nome_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
        tb.Label(main_frame, text="Valor (R$):").grid(row=r, column=0, sticky="w", pady=5); tb.Entry(main_frame, textvariable=valor_var, validate="key", validatecommand=self.vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1

        def salvar():
            n_novo = clean_str(nome_var.get())
            v_novo = float(money_pt(valor_var.get()))
            if not n_novo: return
            if is_edit_mode: db.update_analise(nome_antigo, n_novo, v_novo)
            else: db.add_analise(n_novo, v_novo)
            edit_window.destroy(); self.atualizar_views()

        tb.Button(main_frame, text="Salvar", command=salvar, bootstyle=SUCCESS).pack(side="right", pady=15)

    def submit_registro_event(self, _=None):
        """Salva o novo registro ou a edição no Banco de Dados."""
        # 1. Coleta dados
        try:
            data_str = obter_data_segura(self.entrada_data).strftime("%Y-%m-%d")
        except:
            ModernMessageBox.showerror("Erro", "Data inválida"); return

        parceiro = clean_str(self.parceiro_var.get())
        residuo = clean_str(self.res_var.get())
        tipo = clean_str(self.tipo_var.get())
        estado = clean_str(self.estado_var.get())
        destinacao = clean_str(self.destinacao_var.get())
        modo_atual = clean_str(self.calc_mode_var.get()).lower()
        
        pedido = clean_str(self.entrada_pedido.get()) if tipo.lower() == "custo" else ""
        vkg_input = money_pt(self.entrada_valor_kg.get())
        vfechado = money_pt(self.entrada_valor_fechado.get())
        peso_input = money_pt(self.entrada_peso.get())
        transp = money_pt(self.entrada_transporte.get())

        if not parceiro or not residuo: 
            ModernMessageBox.showerror("Erro", "Preencha Parceiro e Resíduo."); return
        if not destinacao: 
            ModernMessageBox.showerror("Erro", "Selecione Destinação."); return

        peso_kg_input = Decimal("0")
        peso_kg_input = money_pt(self.peso_kg_var.get())
        if modo_atual == "unidade" and peso_kg_input == Decimal("0"):
            self.calcular_peso_kg_automatico()
            peso_kg_input = money_pt(self.peso_kg_var.get()) 

        vkg_a_salvar = Decimal("0"); valor_base = Decimal("0"); total = Decimal("0"); peso_a_salvar_quantidade = Decimal("0")
        peso_a_salvar_kg_opcional = Decimal("0") 
        
        if modo_atual == "kg": 
            if peso_input <= 0: ModernMessageBox.showerror("Erro", "Peso > 0."); return
            peso_a_salvar_quantidade = peso_input; peso_a_salvar_kg_opcional = peso_input
            vkg_a_salvar = vkg_input; valor_base = vkg_a_salvar * peso_a_salvar_quantidade
            total = valor_base + transp; vfechado = Decimal("0")
        elif modo_atual == "unidade": 
            if peso_input <= 0: ModernMessageBox.showerror("Erro", "Quantidade > 0."); return
            peso_a_salvar_quantidade = peso_input; peso_a_salvar_kg_opcional = peso_kg_input 
            vkg_a_salvar = vkg_input; valor_base = vkg_a_salvar * peso_a_salvar_quantidade
            total = valor_base + transp; vfechado = Decimal("0")
        elif modo_atual == "fechado":
            if vfechado <= 0: ModernMessageBox.showerror("Erro", "Valor fechado > 0."); return
            peso_a_salvar_quantidade = peso_input; valor_base = vfechado; total = valor_base + transp
            vkg_a_salvar = Decimal("0"); peso_a_salvar_kg_opcional = peso_kg_input
        else: 
            ModernMessageBox.showerror("Erro", f"Modo '{modo_atual}' inválido."); return

        # Checa Checkboxes
        if self.var_nf_manual.get() == 1: 
            nf_status = "Não" 
            if self.editing_id is not None:
                try: 
                    val_antigo = self.df_registros.loc[self.editing_id, 'NFOk']
                    if val_antigo and val_antigo not in ("N/A", "n/a"): nf_status = val_antigo
                except: pass
        else: nf_status = "N/A"

        if self.var_cert_manual.get() == 1:
            cert_ok = "Não"
            if self.editing_id is not None:
                try: 
                    val_antigo = self.df_registros.loc[self.editing_id, 'CertificadoOK']
                    if val_antigo and val_antigo not in ("N/A", "n/a"): cert_ok = val_antigo
                except: pass
        else: cert_ok = "N/A"

        # Arquivos anexo
        caminho_final = ""
        path_temp = self.caminho_anexo_temp.get()
        if path_temp:
            caminho_final = self.salvar_arquivo_anexo(path_temp, self.editing_id)
        if self.editing_id is not None and not path_temp:
            try: caminho_final = self.df_registros.loc[self.editing_id, 'CaminhoAnexo']
            except: caminho_final = ""

        # Monta a lista pro BD
        data_full_para_db = [ 
            data_str, parceiro, residuo, estado, destinacao, tipo, modo_atual, 
            float(peso_a_salvar_quantidade), float(vkg_a_salvar), float(vfechado), 
            float(transp), float(total), pedido, "", cert_ok, float(peso_a_salvar_kg_opcional),
            "Não", caminho_final
        ]   
        
        try:
            foi_edicao = (self.editing_id is not None)
            if foi_edicao: 
                db.update_registro(self.editing_id, data_full_para_db)
                if hasattr(db, 'update_nf'): db.update_nf(self.editing_id, nf_status)
                self.set_status("Registro atualizado.")
            else: 
                new_id = db.add_registro(data_full_para_db)
                if new_id and new_id != -1 and hasattr(db, 'update_nf'): db.update_nf(new_id, nf_status)
                self.set_status("Registro adicionado.")
                
            self.clear_form()
            self.atualizar_views()
            if foi_edicao: self.nb.select(self.aba_regs)
        except Exception as e: 
            ModernMessageBox.showerror("Erro ao Salvar", f"Detalhes do erro: {e}")

    def salvar_arquivo_anexo(self, origem, id_registro=None):
        import shutil
        if not origem or not os.path.exists(origem): return ""
        pasta_destino = "anexos_registros"
        if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
        try:
            nome_orig = os.path.basename(origem)
            prefixo = f"ID{id_registro}" if id_registro else datetime.now().strftime("%Y%m%d%H%M%S")
            nome_final = f"{prefixo}_{nome_orig}"
            destino_final = os.path.join(pasta_destino, nome_final)
            shutil.copy2(origem, destino_final)
            return destino_final
        except Exception as e:
            return ""

    def selecionar_anexo(self):
        """Abre o explorador de arquivos para anexar um comprovante ou MTR."""
        path = filedialog.askopenfilename(
            title="Selecione o Comprovante/MTR", 
            filetypes=[("Documentos", "*.pdf *.jpg *.png *.jpeg")]
        )
        if path:
            self.caminho_anexo_temp.set(path)
            self.lbl_anexo_info.config(text=f"📎 {os.path.basename(path)}", bootstyle="success")

    def preencher_tabela(self, df):
        for r in self.tabela.get_children(): self.tabela.delete(r)
        if df.empty: return
        
        hoje = date.today()
        for i, row in df.iterrows():
            tags = []
            estado_val = clean_str(row.get("Estado", "")).lower()
            if "sólido" in estado_val or "solido" in estado_val: tags.append("estado_solido")
            elif "líquido" in estado_val or "liquido" in estado_val: tags.append("estado_liquido")
            else: tags.append("evenrow" if i % 2 == 0 else "oddrow")

            cert_val_raw = clean_str(row.get("CertificadoOK", "")).lower()
            is_cert_ok = cert_val_raw in ("sim", "ok", "true", "1", "yes")
            is_cert_na = cert_val_raw in ("n/a", "na", "dispensado")
            
            data_registro = row.get('Data')
            if not is_cert_ok and not is_cert_na and pd.notna(data_registro):
                try:
                    d_reg = data_registro.date() if isinstance(data_registro, datetime) else data_registro
                    if isinstance(d_reg, date) and (hoje - d_reg).days > 30: tags.append("atrasado")
                except: pass

            tipo_val = clean_str(row.get("Tipo", "")).lower()
            if tipo_val == "venda": tags.append("tipo_venda")
            elif tipo_val == "custo": tags.append("tipo_custo")
            
            icon_cert = "✔" if is_cert_ok else ("" if is_cert_na else "✖")
            if icon_cert == "✖": tags.append("cert_nao")

            nf_val_raw = clean_str(row.get("NFOk", "")).lower()
            if nf_val_raw in ("sim", "ok", "true", "1", "yes"): icon_nf = "✔"; tags.append("nf_ok")
            elif "solicitado" in nf_val_raw: icon_nf = "⏳"; tags.append("nf_solicitado")
            elif nf_val_raw in ("n/a", "na", "dispensado"): icon_nf = ""
            else: icon_nf = "✖"; tags.append("nf_nao")

            data_str_fmt = format_data_ptbr_abbrev(pd.Series([row.get('Data', pd.NaT)])).iloc[0]
            peso = to_float_safe(row.get("Peso",0)); vfixo = to_float_safe(row.get("ValorFechado",0)); transp = to_float_safe(row.get("Transporte",0)); vtotal = to_float_safe(row.get("ValorTotal",0))
            transp_display = fmt_moeda(transp) if transp > 0 else ""; vfixo_display = fmt_moeda(vfixo) if vfixo > 0 else ""
            vkg = to_float_safe(row.get("ValorPorKg",0)); modo = clean_str(row.get('Modo',"kg")).lower()
            
            valor_unit_display = fmt_moeda(vkg) if modo in ('kg', 'unidade', 'ton') and vkg > 0 else ""

            peso_display = fmt_kg(peso)
            if modo == 'unidade':
                 s_un = f"{Decimal(str(peso)):.0f}"
                 peso_real_kg = to_float_safe(row.get("PesoEmKg", 0))
                 peso_display = f"{s_un} un ({fmt_kg(peso_real_kg)})" if peso_real_kg > 0 else f"{s_un} un"

            val_res_calc = vtotal - transp
            val_res_display = fmt_moeda(val_res_calc) if val_res_calc > 0 else ""

            values_display = (data_str_fmt, clean_str(row.get('Parceiro',"")), clean_str(row.get('Residuo',"")), clean_str(row.get('Estado',"")), clean_str(row.get('Destinacao',"")), clean_str(row.get('Tipo',"")).capitalize(), peso_display, valor_unit_display, vfixo_display, val_res_display, transp_display, clean_str(row.get("PedidoCompra","")), icon_cert, icon_nf)
            
            self.tabela.insert("", "end", iid=str(i), values=values_display, tags=tuple(tags))

    def aplicar_filtros(self, d):
        if d.empty: return d
        if 'Data' in d.columns:
            d['Data'] = pd.to_datetime(d['Data'], format='%Y-%m-%d', errors='coerce')
            if d['Data'].isna().all(): d['Data'] = pd.to_datetime(d['Data'], errors='coerce')

        try:
            dt_inicio = pd.to_datetime(self.f_data_inicio.get_date())
            dt_fim = pd.to_datetime(self.f_data_fim.get_date()) + timedelta(days=1, seconds=-1)
            d = d.dropna(subset=['Data'])
            d = d[(d["Data"] >= dt_inicio) & (d["Data"] <= dt_fim)]
        except: pass

        if self.f_parc.get() != "Todos" and 'Parceiro' in d.columns: d = d[d["Parceiro"] == self.f_parc.get()]
        if self.f_res.get() != "Todos" and 'Residuo' in d.columns: d = d[d["Residuo"] == self.f_res.get()]
        if self.f_estado.get() != "Todas" and 'Estado' in d.columns: d = d[d["Estado"] == self.f_estado.get()]
        if self.f_dest.get() != "Todas" and 'Destinacao' in d.columns: d = d[d["Destinacao"] == self.f_dest.get()]
        if self.f_tipo.get() != "Todos" and 'Tipo' in d.columns: d = d[d["Tipo"] == self.f_tipo.get()]

        q = clean_str(self.f_busca.get()).lower()
        if q:
            conditions = []
            if 'Parceiro' in d.columns: conditions.append(d["Parceiro"].str.lower().str.contains(q, na=False))
            if 'PedidoCompra' in d.columns: conditions.append(d["PedidoCompra"].astype(str).str.contains(q, na=False))
            if conditions:
                final_condition = conditions[0]
                for cond in conditions[1:]: final_condition = final_condition | cond
                d = d[final_condition] 
            else: return pd.DataFrame(columns=d.columns) 

        if 'Data' in d.columns: d = d.sort_values(by='Data', ascending=True)
        return d

    def aplicar_filtro_rapido(self, periodo):
        hoje = date.today()
        if periodo == "mes": ini = hoje.replace(day=1); fim = hoje
        elif periodo == "ano": ini = hoje.replace(day=1, month=1); fim = hoje
        elif periodo == "tudo": ini = date(2020, 1, 1); fim = hoje
        elif periodo == "mes_passado":
            ultimo_mes_passado = hoje.replace(day=1) - timedelta(days=1)
            ini = ultimo_mes_passado.replace(day=1); fim = ultimo_mes_passado
            
        self.f_data_inicio.set_date(ini)
        self.f_data_fim.set_date(fim)
        self.atualizar_views()

    def limpar_filtros_ui(self):
        self.f_parc.set("Todos"); self.f_res.set("Todos"); self.f_estado.set("Todas")
        self.f_dest.set("Todas"); self.f_tipo.set("Todos"); self.f_busca.set("")
        self.f_data_inicio.set_date(date(2025, 1, 1)); self.f_data_fim.set_date(date.today())
        self.atualizar_views()

    # (Métodos de sincronização de tabelas e comboboxes)
    def preencher_banco_tabela(self):
        self.df_banco = db.get_banco_residuos() 
        self.banco_dict.clear()
        for r in self.bn_tbl.get_children(): self.bn_tbl.delete(r)
        q = normalizar(self.bn_busca.get()) if hasattr(self, "bn_busca") else ""
        row_num = 0
        for i, row in self.df_banco.iterrows():
            residuo_nome = clean_str(row.get("Residuo", ""))
            if not residuo_nome: continue
            self.banco_dict[residuo_nome] = {
                'nome_nf': clean_str(row.get('NomeNF', '')), 'codigo_item': clean_str(row.get('CodigoItem', '')),
                'modo': clean_str(row.get('ModoPadrao', 'kg')).lower(), 'kg': to_float_safe(row.get('ValorPorKgPadrao', 0.0)),
                'fechado': to_float_safe(row.get('ValorFechadoPadrao', 0.0)), 'peso_unitario': to_float_safe(row.get('PesoUnitarioKgPadrao', 0.0)),
                'estado_padrao': clean_str(row.get('EstadoPadrao', '')), 'destinacao_padrao': clean_str(row.get('DestinacaoPadrao', '')),
                'tipo_padrao': clean_str(row.get('TipoPadrao', '')), 'parceiro_padrao': clean_str(row.get('ParceiroPadrao', '')),
                'exige_nf': bool(row.get('ExigeNF', 1)), 'exige_cert': bool(row.get('ExigeCertificado', 1))
            }
            if q and q not in normalizar(residuo_nome) and q not in normalizar(self.banco_dict[residuo_nome]['nome_nf']): continue
            tag = "evenrow" if row_num % 2 == 0 else "oddrow"
            self.bn_tbl.insert("", "end", iid=str(i), values=(residuo_nome, self.banco_dict[residuo_nome]['nome_nf'], self.banco_dict[residuo_nome]['codigo_item'], self.banco_dict[residuo_nome]['modo'], fmt_moeda(self.banco_dict[residuo_nome]['kg']), fmt_moeda(self.banco_dict[residuo_nome]['fechado']), fmt_kg(self.banco_dict[residuo_nome]['peso_unitario'])), tags=(tag,))
            row_num += 1

    def preencher_parceiros_tabela(self):
        self.df_parceiros = db.get_banco_parceiros()
        for r in self.pc_tbl.get_children(): self.pc_tbl.delete(r)
        for i, row in self.df_parceiros.iterrows():
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tipo = clean_str(row.get("TipoParceiro", "Destinador"))
            self.pc_tbl.insert("", "end", iid=str(i), values=(clean_str(row["Parceiro"]), tipo), tags=(tag,))

    def preencher_analises_tabela(self):
        self.df_analises = db.get_banco_analises()
        for r in self.bana_tbl.get_children(): self.bana_tbl.delete(r)
        for i, row in self.df_analises.iterrows():
            nome_analise = clean_str(row.get("NomeAnalise", ""))
            valor_padrao = to_float_safe(row.get("ValorPadrao", 0.0))
            if nome_analise:
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                self.bana_tbl.insert("", "end", iid=str(i), values=(nome_analise, fmt_moeda(valor_padrao)), tags=(tag,))

    def sincronizar_residuos_ui(self):
        self.banco_residuos = sorted(self.df_banco["Residuo"].tolist()) if 'Residuo' in self.df_banco.columns else []    
        self.res_cb.configure(values=self.banco_residuos)
        self.res_menu.configure(values=["Todos"] + self.banco_residuos)

    def sincronizar_parceiros_ui(self):
        if self.df_parceiros.empty:
            self.lista_todos_parceiros = self.lista_destinadores = self.lista_transportadores = self.lista_laboratorios = self.parceiros = []
        else:
            self.lista_todos_parceiros = sorted(self.df_parceiros['Parceiro'].tolist())
            self.parceiros = self.lista_todos_parceiros 
            col = 'TipoParceiro' if 'TipoParceiro' in self.df_parceiros.columns else None
            if col:
                self.lista_destinadores = sorted(self.df_parceiros[self.df_parceiros[col].str.contains('Destinador|Receptor|Final', case=False, na=False)]['Parceiro'].tolist())
                self.lista_transportadores = sorted(self.df_parceiros[self.df_parceiros[col].str.contains('Transportador|Transporte|Logística', case=False, na=False)]['Parceiro'].tolist())
                self.lista_laboratorios = sorted(self.df_parceiros[self.df_parceiros[col].str.contains('Lab|Análise', case=False, na=False)]['Parceiro'].tolist())
            else: self.lista_destinadores = self.lista_transportadores = self.lista_laboratorios = self.lista_todos_parceiros

        self.ana_parc_cb.configure(values=self.lista_laboratorios if self.lista_laboratorios else self.lista_todos_parceiros)
        self.transp_parc_cb.configure(values=self.lista_transportadores if self.lista_transportadores else self.lista_todos_parceiros)
        self.parc_menu.configure(values=["Todos"] + self.lista_todos_parceiros)
        self.atualizar_combobox_parceiro_dinamico()

    def sincronizar_analises_ui(self):
        if not self.df_analises.empty and 'NomeAnalise' in self.df_analises.columns:
            self.lista_analises = sorted(self.df_analises["NomeAnalise"].tolist())
            self.analises_dict = {row['NomeAnalise']: to_float_safe(row.get('ValorPadrao', 0.0)) for _, row in self.df_analises.iterrows() if clean_str(row.get("NomeAnalise", ""))}
        else: self.lista_analises = []; self.analises_dict = {}
        self.ana_nome_cb.configure(values=self.lista_analises)
        self.atualizar_valor_por_analise()

    def sincronizar_destinacoes_ui(self):
        destinacoes_unicas = self.df_registros["Destinacao"].unique().tolist() if not self.df_registros.empty else []
        self.destinacoes = sorted(list(set(self.DEFAULT_DESTINACOES + [d for d in destinacoes_unicas if d])))
        self.destinacao_cb.configure(values=self.destinacoes)
        if not self.destinacao_var.get() and self.destinacoes: self.destinacao_var.set(self.destinacoes[0])

    def atualizar_menus_dinamicos(self, base):
        if base.empty: parc_set, res_set, dest_set = [], [], []
        else:
            parc_set=sorted({clean_str(x) for x in base["Parceiro"].astype("string").fillna("") if clean_str(x)})
            res_set=sorted({clean_str(x) for x in base["Residuo"].astype("string").fillna("") if clean_str(x)})
            dest_set=sorted({clean_str(x) for x in base["Destinacao"].astype("string").fillna("") if clean_str(x)})
        self.parc_menu.configure(values=["Todos"] + parc_set)
        self.res_menu.configure(values=["Todos"] + res_set)
        self.dest_menu.configure(values=["Todas"] + dest_set)

    def preencher_pendencias(self):
        for r in self.pend_tbl.get_children(): self.pend_tbl.delete(r)
        df_pend = db.get_pending_certificates()
        if not df_pend.empty and 'CertificadoOK' in df_pend.columns:
            mask = ~df_pend['CertificadoOK'].astype(str).str.lower().isin(['n/a', 'na', 'dispensado', 'não aplicável', 'nao aplicavel'])
            df_pend = df_pend[mask]
            df_pend['Data_fmt'] = format_data_ptbr_abbrev(df_pend['Data'])
            for i, (db_id, row) in enumerate(df_pend.iterrows()):
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                self.pend_tbl.insert("", "end", iid=str(db_id), values=(row['Data_fmt'], clean_str(row.get('Parceiro', '')), clean_str(row.get('Residuo', ''))), tags=(tag,))

    # ==============================================================================
    # EXPORTAÇÃO
    # ==============================================================================
    def exportar_para_excel(self):
        df_filtrado = self.aplicar_filtros(self.df_registros.copy())
        if df_filtrado.empty: 
            ModernMessageBox.showinfo("Exportar", "Nenhum dado filtrado para exportar.")
            return
            
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Arquivo Excel", "*.xlsx")], initialfile=f"Relatorio_Residuos_{datetime.now():%Y-%m-%d}.xlsx", title="Salvar Relatório Excel")
        if not path: return

        df_totais = calculos.resumo_mensal_df(df_filtrado)[0] # Simulando chamada, em seu código use seu atualizar_totais original
        df_resumo_raw, _ = calculos.resumo_mensal_df(df_filtrado)
        exportacao.gerar_excel_tabela(self.root, path, df_totais, df_resumo_raw, df_filtrado)

    def realizar_backup_e_fechar(self):
        import shutil
        try:
            pasta_backup = "Backups"
            if not os.path.exists(pasta_backup): os.makedirs(pasta_backup)
            arquivo_origem = "residuos_db.sqlite" 
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            arquivo_destino = os.path.join(pasta_backup, f"backup_{timestamp}.sqlite")
            if os.path.exists(arquivo_origem):
                shutil.copy2(arquivo_origem, arquivo_destino)
                lista_backups = sorted([os.path.join(pasta_backup, f) for f in os.listdir(pasta_backup)], key=os.path.getmtime)
                while len(lista_backups) > 50: os.remove(lista_backups.pop(0))
        except: pass
        self.root.destroy()

# ==========================================
# EXECUÇÃO DO APLICATIVO
# ==========================================
if __name__ == "__main__":
    app_root = tb.Window(themename="yeti")
    app = SistemaGestaoAmbiental(app_root)
    app_root.mainloop()
