# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── Coleta dinâmica de pacotes com muitos submódulos ──────────────────────────
uvicorn_d,   uvicorn_b,   uvicorn_h   = collect_all('uvicorn')
fastapi_d,   fastapi_b,   fastapi_h   = collect_all('fastapi')
starlette_d, starlette_b, starlette_h = collect_all('starlette')
pydantic_d,  pydantic_b,  pydantic_h  = collect_all('pydantic')

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
    'routers.pedidos', 'routers.pedidos_venda', 'routers.precificacoes',
    'routers.tabelas_preco', 'routers.tecidos', 'routers.vendedor_painel', 'routers.vendedores',
    # models
    'models', 'models.encaixe', 'models.financeiro', 'models.grupo_molde',
    'models.molde', 'models.painel_vendedor', 'models.pedido', 'models.precificacao',
    'models.tecido', 'models.venda',
    # services
    'services', 'services.auth_service', 'services.cor_service', 'services.defeito_service',
    'services.encaixe_service', 'services.gramatura_service', 'services.grupo_service',
    'services.lote_service', 'services.modelo_service', 'services.molde_service',
    'services.nesting_service', 'services.pdf_venda_service', 'services.pedido_service',
    'services.precificacao_service', 'services.report_service',
    'services.tecido_service', 'services.venda_service',
    # schemas
    'schemas', 'schemas.encaixe_schema', 'schemas.financeiro_schema', 'schemas.molde_schema',
    'schemas.pedido_schema', 'schemas.precificacao_schema',
    'schemas.tecido_schema', 'schemas.venda_schema',
    # parsers / nesting
    'parsers', 'parsers.ads_parser', 'parsers.dxf_parser', 'parsers.plt_parser',
    'nesting', 'nesting.nesting_bridge',
    # auth / JWT
    'jose', 'jose.jwt', 'jose.exceptions', 'jose.constants',
    'passlib', 'passlib.context', 'passlib.handlers', 'passlib.handlers.bcrypt',
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
    'qrcode',
    'qrcode.image.pil',
    'qrcode.image.base',
    'qrcode.constants',
    'qrcode.main',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'shapely', 'shapely.geometry',
    'ezdxf',
]

all_hidden = (
    uvicorn_h + fastapi_h + starlette_h + pydantic_h +
    sqlalchemy_h + pydantic_settings_h + anyio_h +
    app_h
)

all_datas = (
    uvicorn_d + fastapi_d + starlette_d + pydantic_d +
    # Arquivos de nesting (js) necessários em runtime
    [('nesting/nest_worker.js', 'nesting'),
     ('nesting/svgnest',        'nesting/svgnest')]
)

all_binaries = uvicorn_b + fastapi_b + starlette_b + pydantic_b

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
