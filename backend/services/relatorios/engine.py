"""Motor de relatórios configuráveis (RL1).

Mesmo esquema do ERP atual (DevMaster/DevExpress): modelos HTML + CSS com
placeholders Jinja2, variantes por relatório e um modelo padrão. O PDF é
gerado pelo Electron (RL2) a partir do HTML devolvido aqui.

A pasta é local, dentro da estrutura do SmartCut, versionada no Git e
editada pelo Explorer do Windows — o sistema SÓ LÊ (não há tela de gestão).
Os arquivos são lidos a cada impressão, sem cache.

Pasta (<raiz do SmartCut>/relatorios; SMARTCUT_RELATORIOS_DIR sobrescreve):
    vendas/relVen001.html              modelo principal
    vendas/relVen001_<variante>.html   variantes
    producao/relPro001.html            formulário de corte da Ordem de Corte
    _comum/                            partes comuns: {% include "_comum/cabecalho_empresa.html" %}
    assets/                            logo e imagens — asset("logo.png")
    config.json                        {"relVen001": {"padrao": "relVen001.html"}, ...}
"""

from __future__ import annotations

import base64
import io
import json
import logging
import mimetypes
import os
import re
import sys
import threading
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from jinja2 import FileSystemLoader, TemplateError, TemplateNotFound, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy.orm import Session

from services.relatorios import dados_ordem_corte, dados_pedido

logger = logging.getLogger(__name__)

# ── Registro de relatórios ────────────────────────────────────────────────────
# Códigos seguem o ERP (relVen001 = Pedido de venda). fonte_dados(db, id)
# devolve o contexto do modelo; permissao é o módulo exigido para imprimir.


@dataclass(frozen=True)
class Relatorio:
    modulo: str
    titulo: str
    fonte_dados: Callable[[Session, str], dict]
    permissao: str


REGISTRO: dict[str, Relatorio] = {
    "relVen001": Relatorio(
        modulo="vendas",
        titulo="Pedido de venda",
        fonte_dados=dados_pedido.montar,
        permissao="pedidos_ver",
    ),
    "relPro001": Relatorio(
        modulo="producao",
        titulo="Formulário de corte",
        fonte_dados=dados_ordem_corte.montar,
        permissao="encaixes",
    ),
}

_CONFIG = "config.json"
_ASSETS = "assets"
_COMUM = "_comum"


class ErroRelatorio(Exception):
    """Relatório/arquivo inexistente ou inválido (router → 404/400)."""

    def __init__(self, mensagem: str, status: int = 404):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


class ErroModelo(Exception):
    """Erro no modelo editado pelo usuário (router → 422 com linha)."""

    def __init__(self, arquivo: str, linha: int | None, mensagem: str):
        super().__init__(mensagem)
        self.arquivo = arquivo
        self.linha = linha
        self.mensagem = mensagem

    def texto(self) -> str:
        onde = f"{self.arquivo}, linha {self.linha}" if self.linha else self.arquivo
        return f"Erro no modelo {onde}: {self.mensagem}"


# ── Pasta ─────────────────────────────────────────────────────────────────────


def relatorios_dir() -> Path:
    """SMARTCUT_RELATORIOS_DIR ou <raiz do SmartCut>/relatorios (mesmo nível
    de backend/ e frontend/). No executável (PyInstaller) não há raiz do
    projeto: sem a variável, usa a pasta do executável."""
    env = os.getenv("SMARTCUT_RELATORIOS_DIR", "").strip()
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "relatorios"
    return Path(__file__).resolve().parents[3] / "relatorios"


def garantir_pasta() -> Path:
    """Cria relatorios/, assets/, _comum/, as pastas dos módulos e o
    config.json (principal de cada relatório como padrão) — só o que
    faltar: relatório novo no REGISTRO ganha entrada no config.json
    existente, sem mexer nas escolhas já feitas."""
    pasta = relatorios_dir()
    for sub in (_ASSETS, _COMUM, *{r.modulo for r in REGISTRO.values()}):
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    config = pasta / _CONFIG
    # config.json existente mas ilegível fica como está (_ler_config avisa no log).
    atual = _ler_config() if config.exists() else {}
    if config.exists() and not atual:
        return pasta
    faltando = {codigo: {"padrao": f"{codigo}.html"} for codigo in REGISTRO if codigo not in atual}
    if faltando:
        config.write_text(json.dumps({**atual, **faltando}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pasta


# ── Variantes / padrão ────────────────────────────────────────────────────────


def _relatorio(codigo: str) -> Relatorio:
    rel = REGISTRO.get(codigo)
    if rel is None:
        raise ErroRelatorio(f"Relatório {codigo} não existe.")
    return rel


def _eh_do_relatorio(codigo: str, arquivo: str) -> bool:
    # relVen001.html ou relVen001_<variante>.html — só nome, sem caminho.
    return bool(re.fullmatch(rf"{re.escape(codigo)}(_[\w\-]+)?\.html", arquivo))


def _arquivos(codigo: str) -> list[str]:
    """Arquivos relVen001*.html da pasta do módulo (principal primeiro)."""
    pasta = relatorios_dir() / _relatorio(codigo).modulo
    if not pasta.is_dir():
        return []
    nomes = [p.name for p in pasta.glob(f"{codigo}*.html") if p.is_file() and _eh_do_relatorio(codigo, p.name)]
    return sorted(nomes, key=lambda n: (n != f"{codigo}.html", n.lower()))


def _ler_config() -> dict:
    caminho = relatorios_dir() / _CONFIG
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("[relatorios] %s inválido, ignorado: %s", caminho, exc)
        return {}


def padrao(codigo: str, arquivos: list[str] | None = None) -> str:
    """config.json → {"<codigo>": {"padrao": "<arquivo>"}}. Ausente ou
    arquivo inexistente → <codigo>.html (com aviso no log)."""
    arquivos = _arquivos(codigo) if arquivos is None else arquivos
    principal = f"{codigo}.html"
    entrada = _ler_config().get(codigo)
    escolhido = entrada.get("padrao") if isinstance(entrada, dict) else None
    if not escolhido:
        logger.warning("[relatorios] %s sem padrão no config.json — usando %s", codigo, principal)
        return principal
    if escolhido not in arquivos:
        logger.warning("[relatorios] padrão de %s (%s) não existe na pasta — usando %s", codigo, escolhido, principal)
        return principal
    return escolhido


def variantes(codigo: str) -> list[dict]:
    """[{arquivo, padrao}] dos modelos do relatório na pasta."""
    arquivos = _arquivos(codigo)
    escolhido = padrao(codigo, arquivos)
    return [{"arquivo": a, "padrao": a == escolhido} for a in arquivos]


def resolver_variante(codigo: str, variante: str | None) -> str:
    """Arquivo a renderizar: sem variante → padrão; aceita o nome do arquivo
    ("relVen001_resumido.html") ou só o sufixo ("resumido")."""
    arquivos = _arquivos(codigo)
    if not variante:
        arquivo = padrao(codigo, arquivos)
    elif variante.endswith(".html"):
        arquivo = variante
    else:
        arquivo = f"{codigo}_{variante}.html"
    if arquivo not in arquivos:
        raise ErroRelatorio(f"Modelo {arquivo} não encontrado na pasta de relatórios.")
    return arquivo


# ── Filtros pt-BR ─────────────────────────────────────────────────────────────


def _decimal(valor: Any) -> Decimal:
    try:
        return Decimal(str(valor)) if valor not in (None, "") else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def f_numero(valor: Any, casas: int = 2) -> str:
    """1234.5 → "1.234,50" (casas decimais configuráveis)."""
    texto = f"{_decimal(valor):,.{int(casas)}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def f_moeda(valor: Any) -> str:
    """1234.56 → "R$ 1.234,56"; negativo → "-R$ 1,00"."""
    d = _decimal(valor)
    return f"-R$ {f_numero(-d)}" if d < 0 else f"R$ {f_numero(d)}"


def f_data(valor: Any) -> str:
    """date/datetime/"AAAA-MM-DD..." → "DD/MM/AAAA"; vazio → ""."""
    if not valor:
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(valor))
    return f"{m[3]}/{m[2]}/{m[1]}" if m else str(valor)


def _digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def f_cnpj_cpf(valor: Any) -> str:
    d = _digitos(valor)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(valor or "")


def f_cep(valor: Any) -> str:
    d = _digitos(valor)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else str(valor or "")


def f_telefone(valor: Any) -> str:
    d = _digitos(valor)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return str(valor or "")


# ── Assets (data URI) ─────────────────────────────────────────────────────────


# Imagem mais larga que isso vira uma cópia reduzida (só no data URI; o
# arquivo da pasta fica intacto): logo gigante pesa no HTML e no PDF.
_LARGURA_MAX_ORIGINAL = 1000
_LARGURA_REDUZIDA = 800

# caminho → ((mtime_ns, tamanho), data URI). Invalida quando o arquivo muda.
_cache_data_uri: dict[str, tuple[tuple[int, int], str]] = {}
_cache_lock = threading.Lock()


def _bytes_da_imagem(caminho: Path, mime: str) -> tuple[bytes, str]:
    """Bytes para o data URI: o original, ou PNG reduzido a 800 px de
    largura se a imagem tiver mais de 1000 px (Pillow; sem Pillow ou
    arquivo que não é imagem → original)."""
    dados = caminho.read_bytes()
    if not mime.startswith("image/") or mime == "image/svg+xml":
        return dados, mime
    try:
        from PIL import Image

        with Image.open(io.BytesIO(dados)) as img:
            if img.width <= _LARGURA_MAX_ORIGINAL:
                return dados, mime
            altura = max(1, round(img.height * _LARGURA_REDUZIDA / img.width))
            reduzida = img.convert("RGBA").resize((_LARGURA_REDUZIDA, altura), Image.LANCZOS)
            saida = io.BytesIO()
            reduzida.save(saida, format="PNG", optimize=True)
            logger.info("[relatorios] %s reduzido de %dpx para %dpx", caminho.name, img.width, _LARGURA_REDUZIDA)
            return saida.getvalue(), "image/png"
    except Exception as exc:  # noqa: BLE001 — imagem ilegível: usa o original
        logger.warning("[relatorios] não foi possível reduzir %s: %s", caminho.name, exc)
        return dados, mime


def arquivo_data_uri(caminho: Path) -> str:
    """Arquivo → data:<mime>;base64,... ("" se não existir). Em cache na
    memória, invalidado pela data de modificação/tamanho do arquivo."""
    try:
        info = caminho.stat()
    except OSError:
        return ""
    if not caminho.is_file():
        return ""
    chave = str(caminho.resolve())
    versao = (info.st_mtime_ns, info.st_size)
    with _cache_lock:
        em_cache = _cache_data_uri.get(chave)
    if em_cache and em_cache[0] == versao:
        return em_cache[1]

    mime = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
    dados, mime = _bytes_da_imagem(caminho, mime)
    uri = f"data:{mime};base64,{base64.b64encode(dados).decode('ascii')}"
    with _cache_lock:
        _cache_data_uri[chave] = (versao, uri)
    return uri


def _asset(nome: str) -> str:
    """asset("logo.png") no modelo: imagem de assets/ embutida. Só arquivos
    dentro de assets/ — caminho que escapa da pasta devolve ""."""
    pasta = (relatorios_dir() / _ASSETS).resolve()
    caminho = (pasta / str(nome)).resolve()
    if pasta not in caminho.parents:
        return ""
    return arquivo_data_uri(caminho)


# ── Renderização ──────────────────────────────────────────────────────────────


def _ambiente(pasta: Path) -> SandboxedEnvironment:
    # Sandbox: o modelo é editável pelo usuário. O loader na raiz da pasta
    # permite {% include "_comum/cabecalho_empresa.html" %} (partes comuns
    # a todos os relatórios) sem sair dela — o loader recusa "..".
    # Ambiente novo a cada impressão e cache_size=0: o modelo é sempre lido
    # do disco (edição pelo Explorer vale na próxima impressão).
    env = SandboxedEnvironment(
        loader=FileSystemLoader(str(pasta), encoding="utf-8"),
        cache_size=0,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(
        moeda=f_moeda,
        numero=f_numero,
        data=f_data,
        cnpj_cpf=f_cnpj_cpf,
        cep=f_cep,
        telefone=f_telefone,
    )
    env.globals["asset"] = _asset
    return env


def _local_do_erro(exc: BaseException, pasta: Path, arquivo: str) -> tuple[str, int | None]:
    """Último frame do traceback dentro de um modelo da pasta (o Jinja
    reescreve os frames com o arquivo/linha do template)."""
    raiz = os.path.normcase(str(pasta))
    local: tuple[str, int | None] = (arquivo, None)
    tb = exc.__traceback__
    while tb is not None:
        nome = os.path.normcase(tb.tb_frame.f_code.co_filename)
        if nome.startswith(raiz):
            local = (Path(tb.tb_frame.f_code.co_filename).name, tb.tb_lineno)
        tb = tb.tb_next
    return local


def renderizar(db: Session, codigo: str, id_registro: str, variante: str | None = None) -> str:
    """HTML do relatório com os dados do registro. Erro no modelo → ErroModelo."""
    rel = _relatorio(codigo)
    arquivo = resolver_variante(codigo, variante)
    contexto = rel.fonte_dados(db, id_registro)
    agora = datetime.now()
    contexto["impressao"] = {
        "data": agora.date(),
        "hora": agora.strftime("%H:%M"),
        "nome_relatorio": rel.titulo,
        "codigo": codigo,
        "modelo": arquivo,
    }

    pasta = relatorios_dir()
    env = _ambiente(pasta)
    try:
        return env.get_template(f"{rel.modulo}/{arquivo}").render(contexto)
    except TemplateSyntaxError as exc:
        nome = Path(exc.filename).name if exc.filename else arquivo
        raise ErroModelo(nome, exc.lineno, exc.message or str(exc)) from exc
    except TemplateNotFound as exc:
        raise ErroModelo(arquivo, None, f"arquivo incluído não encontrado: {exc.name}") from exc
    except (TemplateError, TypeError, ValueError, AttributeError, KeyError, ZeroDivisionError) as exc:
        # Erro em tempo de execução (variável indefinida usada, filtro com
        # tipo errado, acesso bloqueado pela sandbox…).
        nome, linha = _local_do_erro(exc, pasta, arquivo)
        raise ErroModelo(nome, linha, str(exc)) from exc
