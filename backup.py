# backup.py
import os
import shutil
from datetime import datetime
from componentes import ModernMessageBox

def realizar_copia_seguranca(app):
    """Cria uma cópia exata da base de dados sempre que o programa é fechado."""
    try:
        pasta_backup = "backups_sistema"
        if not os.path.exists(pasta_backup): 
            os.makedirs(pasta_backup)
        
        arquivo_origem = "residuos_db.sqlite" 
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        arquivo_destino = os.path.join(pasta_backup, f"backup_{timestamp}.sqlite")
        
        if os.path.exists(arquivo_origem):
            shutil.copy2(arquivo_origem, arquivo_destino)
            print(f"Cópia de segurança guardada com sucesso em: {arquivo_destino}")
            
            # Mantém apenas as últimas 50 cópias para não sobrecarregar o computador
            lista_backups = sorted([os.path.join(pasta_backup, f) for f in os.listdir(pasta_backup)], key=os.path.getmtime)
            while len(lista_backups) > 50:
                os.remove(lista_backups.pop(0))
                
    except Exception as erro:
        ModernMessageBox.showwarning("Aviso de Segurança", f"Não foi possível criar a cópia de segurança:\n{erro}", parent=app)

def encerrar_sistema(app):
    """Processo seguro para fechar a janela."""
    realizar_copia_seguranca(app)
    try:
        app.destroy()
    except Exception:
        pass
