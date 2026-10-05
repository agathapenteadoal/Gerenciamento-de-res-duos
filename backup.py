# backup.py
"""Backup automático do banco de dados: 1 cópia por dia, guardando os últimos 60 dias."""
import os
import re
import sqlite3
from datetime import date, timedelta

PASTA_BACKUP = "Backups"
DIAS_GUARDADOS = 60
_PADRAO_NOME = re.compile(r"^backup_(\d{4}-\d{2}-\d{2}).*\.sqlite$")


def fazer_backup_diario(arquivo_banco="residuos_db.sqlite"):
    """Salva a cópia do dia em Backups/backup_AAAA-MM-DD.sqlite e apaga as cópias antigas.

    Se o programa for fechado várias vezes no mesmo dia, a cópia do dia é
    substituída pela mais recente, sem apagar as cópias de dias anteriores.
    Devolve o caminho da cópia criada (ou None se o banco não existir).
    """
    if not os.path.exists(arquivo_banco):
        return None

    pasta = os.path.join(os.path.dirname(os.path.abspath(arquivo_banco)), PASTA_BACKUP)
    os.makedirs(pasta, exist_ok=True)

    destino = os.path.join(pasta, f"backup_{date.today().isoformat()}.sqlite")
    temporario = destino + ".tmp"

    # Usa a cópia própria do SQLite (segura mesmo com o banco em uso) e só
    # substitui a cópia do dia depois que a nova estiver completa.
    origem = sqlite3.connect(arquivo_banco)
    try:
        copia = sqlite3.connect(temporario)
        try:
            origem.backup(copia)
        finally:
            copia.close()
    finally:
        origem.close()
    os.replace(temporario, destino)

    limpar_backups_antigos(pasta)
    return destino


def limpar_backups_antigos(pasta):
    """Mantém só 1 cópia por dia (a mais recente) e apaga as de mais de DIAS_GUARDADOS dias."""
    limite = (date.today() - timedelta(days=DIAS_GUARDADOS)).isoformat()
    por_dia = {}
    for nome in os.listdir(pasta):
        m = _PADRAO_NOME.match(nome)
        if not m:
            continue  # Não mexe em arquivos que não foram criados pelo backup automático
        por_dia.setdefault(m.group(1), []).append(os.path.join(pasta, nome))

    for dia, arquivos in por_dia.items():
        arquivos.sort(key=os.path.getmtime)
        apagar = arquivos if dia < limite else arquivos[:-1]
        for arq in apagar:
            try:
                os.remove(arq)
            except OSError:
                pass
