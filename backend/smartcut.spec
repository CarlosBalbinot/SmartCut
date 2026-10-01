# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Coleta dinâmica de pacotes com muitos submódulos ──────────────────────────
uvicorn_d,   uvicorn_b,   uvicorn_h   = collect_all('uvicorn')
fastapi_d,   fastapi_b,   fastapi_h   = collect_all('fastapi')
starlette_d, starlette_b, starlette_h = collect_all('starlette')
pydantic_d,  pydantic_b,  pydantic_h  = collect_all('pydantic')
# Motor de encaixe (services/nesting_v2): spyrrow (extensão Rust) e
# OR-Tools CP-SAT. O OR-Tools carrega as DLLs de ortools/.libs/ por caminho
# relativo ao próprio __init__ (WinDLL em _load_ortools_libs) — sem o
# collect_all elas não entram no exe e o motor de encaixe não funciona.
spyrrow_d,   spyrrow_b,   spyrrow_h   = collect_all('spyrrow')
ortools_d,   ortools_b,   ortools_h   = collect_all('ortools')

sqlalchemy_h        = collect_submodules('sqlalchemy')
pydantic_settings_h = collect_submodules('pydantic_settings')
anyio_h             = collect_submodules('anyio')
email_validator_h   = collect_submodules('email_validator') if True else []

# ── Módulos locais da aplicação ───────────────────────────────────────────────
app_h = [
    # routers
    'routers', 'routers.auth', 'routers.catalogos', 'routers.configuracao_empresa',
    'routers.cores_tecido', 'routers.encaixes', 'routers.financeiro',
    'routers.grupos_molde', 'routers.grupos_preco', 'routers.leads',
    'routers.lotes_tecido', 'routers.modelos_tecido', 'routers.moldes',
    'routers.pedidos_venda', 'routers.precificacoes',
    'routers.tabelas_preco', 'routers.vendedor_painel', 'routers.vendedores',
    'routers.uploads',
    # models
    'models', 'models.encaixe', 'models.financeiro', 'models.grupo_molde',
    'models.molde', 'models.painel_vendedor', 'models.pedido', 'models.precificacao',
    'models.tecido', 'models.venda',
    # services
    'services', 'services.auth_service', 'services.cor_service',
    'services.encaixe_service', 'services.gramatura_service', 'services.grupo_service',
    'services.lote_service', 'services.modelo_service', 'services.molde_service',
    'services.nesting_service',
    'services.precificacao_service', 'services.rate_limit',
    'services.venda_service', 'services.backup_service',
    'services.segredo_service', 'services.db_migracoes',
    # scripts (backup SQLite — item 3.3)
    'scripts', 'scripts.backup_sqlite',
    # schemas
    'schemas', 'schemas.encaixe_schema', 'schemas.financeiro_schema', 'schemas.molde_schema',
    'schemas.precificacao_schema',
    'schemas.tecido_schema', 'schemas.venda_schema',
    # parsers / motor de encaixe
    'parsers', 'parsers.ads_parser', 'parsers.dxf_parser', 'parsers.plt_parser',
    'services.nesting_v2', 'services.nesting_v2.encaixador',
    'services.nesting_v2.geometria', 'services.nesting_v2.motor',
    'services.nesting_v2.planejador',
    # auth / JWT (PyJWT + bcrypt puro — python-jose e passlib não são mais usados)
    'jwt',
    'bcrypt',
    # SQLite dialect
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.base',
    'sqlalchemy.dialects.sqlite.pysqlite',
    # utilidades
    'dotenv',
    'multipart',
    'h11',
    'click',
    'sniffio',
    'reportlab', 'reportlab.pdfgen', 'reportlab.pdfgen.canvas',
    'reportlab.lib', 'reportlab.lib.pagesizes', 'reportlab.lib.units',
    'reportlab.platypus',
    'reportlab.graphics.barcode',
    'reportlab.graphics.barcode.code93',
    'reportlab.graphics.barcode.code128',
    'reportlab.graphics.barcode.code39',
    'reportlab.graphics.barcode.usps',
    'reportlab.graphics.barcode.usps4s',
    'reportlab.graphics.barcode.ecc200datamatrix',
    'reportlab.graphics.barcode.eanbc',
    'reportlab.graphics.barcode.fourstate',
    'reportlab.graphics.barcode.lto',
    'reportlab.graphics.barcode.qr',
    'reportlab.graphics.barcode.widgets',
    'reportlab.graphics.barcode.common',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'shapely', 'shapely.geometry',
    'ezdxf',
    # Alembic (item 5.2) + Mako (templates de migração)
    'alembic',
    'alembic.config', 'alembic.runtime.migration', 'alembic.ddl.sqlite',
    'alembic.operations', 'alembic.autogenerate',
    'mako', 'mako.template', 'mako.lookup', 'mako.runtime',
]

all_hidden = (
    uvicorn_h + fastapi_h + starlette_h + pydantic_h +
    spyrrow_h + ortools_h +
    sqlalchemy_h + pydantic_settings_h + anyio_h +
    app_h
)

all_datas = (
    uvicorn_d + fastapi_d + starlette_d + pydantic_d +
    spyrrow_d + ortools_d +
    # Alembic (item 5.2): config + env + template + migrações versionadas
    # (baseline). O boot roda alembic upgrade head (services/db_migracoes.py).
    [('alembic.ini',             '.'),
     ('alembic/env.py',          'alembic'),
     ('alembic/script.py.mako',  'alembic'),
     ('alembic/versions',        'alembic/versions')]
)

all_binaries = uvicorn_b + fastapi_b + starlette_b + pydantic_b + spyrrow_b + ortools_b

a = Analysis(
    ['server.py'],
    pathex=['.'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['psycopg2', 'psycopg2_binary', 'PyQt5', 'tkinter', 'pytest', 'matplotlib'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='smartcut-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,      # True = subsistema console; windowsHide=True no Electron esconde a janela
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
