import logging
import secrets
import sys
from pathlib import Path

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./smartcut.db"
    secret_key: str = ""
    # Legado: a pasta de uploads é sempre <pasta de dados>/uploads
    # (services/pasta_dados.py). Mantido só para não recusar UPLOAD_DIR
    # em .env/compose antigos.
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    nesting_timeout_sec: int = 120
    # Cookie de sessão (item 1.4): em produção atrás de HTTPS defina
    # COOKIE_SECURE=true no ambiente/compose para marcar o cookie como Secure.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # Backup automático do SQLite (item 3.3): o backend copia periodicamente
    # o banco (com WAL checkpoint) para uma pasta de backup, mantendo N dias.
    # Só tem efeito quando o banco é SQLite (desktop); no Docker/Postgres o
    # backup é um serviço pg_dump no docker-compose.prod.yml.
    backup_dir: str = ""  # vazio = pasta "backups" ao lado do arquivo .db
    backup_retention_dias: int = 7
    backup_interval_sec: int = 21600  # 6h; segundo backup roda no startup

    # Certificado digital NF-e (itens 4.1 e 4.2).
    # certificado_dir: pasta padrão do .pfx (fora da árvore de código). No
    # desktop o Electron injeta userData/Certificados via CERTIFICADO_DIR.
    # Se vazio, não há pasta padrão — o caminho vem da configuração da empresa
    # (escolhido pelo usuário com o diálogo nativo, item 4.1).
    certificado_dir: str = ""
    # Chave mestre para cifrar segredos em repouso (senha do certificado,
    # item 4.2). Docker/servidor: defina CERT_SENHA_KEY no ambiente. Desktop:
    # o Electron gera a chave por instalação e injeta via SMARTCUT_CERT_KEY —
    # aqui fica vazia. Nunca derive de SECRET_KEY (efêmera no desktop).
    cert_senha_key: str = ""

    # ── Item 10.4: fonte ÚNICA de configuração (settings do pydantic) ──────
    # Variáveis antes lidas via os.getenv espalhado agora vêm daqui; o arquivo
    # .env carregado é sempre backend/.env (caminho absoluto relativo a este
    # arquivo — independente do CWD, inclusive no Docker). Prioridade:
    # variável de ambiente do processo > backend/.env > defaults.

    # SMARTCUT_DB_PATH — caminho do smartcut.db injetado pelo Electron
    # empacotado (userData). Vazio = usa DATABASE_URL normalmente.
    smartcut_db_path: str = ""
    # SMARTCUT_DADOS_DIR — pasta base dos arquivos do usuário (anexos, logo,
    # NF-e, moldes...) injetada pelo Electron empacotado (userData). Vazio =
    # backend/ (desenvolvimento/Docker). Ver services/pasta_dados.py.
    smartcut_dados_dir: str = ""
    # SMARTCUT_CERT_KEY — chave de cifragem dos segredos em repouso injetada
    # pelo Electron (item 4.2). Vazio fora do desktop.
    smartcut_cert_key: str = ""

    model_config = {"env_file": str(Path(__file__).resolve().parent / ".env")}

    _segredo_efemero: str | None = PrivateAttr(default=None)

    @property
    def jwt_segredo(self) -> str:
        """Segredo JWT único do sistema (painel do vendedor + administrativo).

        Fonte única de resolução (item 1.1): SECRET_KEY, vinda da variável de
        ambiente real ou de backend/.env (lido pelo pydantic-settings).

        Sem nenhum segredo configurado, gera um segredo efêmero forte por boot
        e avisa no startup — nunca, em hipótese alguma, uma string fixa em
        código. Em produção o Electron fornece o segredo via ambiente; sem ele,
        os tokens caducam a cada reinício (ver Parte 6.3).
        """
        valor = (self.secret_key or "").strip()
        if valor:
            return valor

        if self._segredo_efemero is None:
            self._segredo_efemero = secrets.token_urlsafe(48)
            aviso = (
                "SECRET_KEY não definido (variável de ambiente ou backend/.env). "
                "Usando segredo JWT efêmero gerado neste boot — tokens serão "
                "invalidados no próximo reinício. Defina SECRET_KEY em produção."
            )
            logging.getLogger("smartcut.config").warning(aviso)
            print(f"[config] AVISO: {aviso}", file=sys.stderr)

        return self._segredo_efemero


settings = Settings()

# Força a resolução do segredo no startup, emitindo o warning de ausência
# antes de qualquer requisição usar o JWT.
_ = settings.jwt_segredo
