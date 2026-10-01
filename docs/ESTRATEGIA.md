# SmartCut — Ideias de diferencial e estratégia

Criado em 01/10/2026 a partir das ideias discutidas nesse dia. Atualizar
conforme as ideias forem entrando no sistema. A ordem de execução fica no
roadmap de [ARQUITETURA.md](ARQUITETURA.md#6-roadmap).

## Visão geral

O SmartCut vai ganhar mercado como **ponte entre o pedido e o corte**, não
como substituto do ERP do cliente.

## Estratégia de produto

- Confecções com ERP raramente trocam de sistema: elas vão adicionando
  módulos ao que já usam.
- Por isso o SmartCut é modular: pode ser o ERP completo da empresa ou um
  acessório plugado no ERP de terceiros e em plataformas online.
- O **módulo de conexão (pedido → corte)** é o principal produto de venda,
  porque é a entrada mais fácil.
- Preço abaixo dos concorrentes ajuda a entrar, mas sozinho não segura
  cliente. O preço precisa vir junto de uma dor que ninguém resolve bem.

### Como o Corte avulso é vendido e instalado

- **Um computador só**: o Corte vendido avulso roda numa máquina (servidor e
  estação juntos), ainda com SQLite. PostgreSQL e vários usuários na rede
  ficam para depois. Se a conversa com as confecções mostrar vários usuários
  simultâneos no corte, essa fase sobe na fila.
- **Pronto para instalar no cliente** (F4): tela de login redesenhada,
  primeiro uso guiado (dados da empresa, primeiro tecido, primeiros moldes),
  regras de senha, perfis prontos (Administrador, PCP, Cortador), registro
  de quem fez o quê nas OCs, licença por módulo com ativação e instalador
  assinado (sem o aviso de "editor desconhecido" do Windows).
- **Fica para depois**: o ERP (vendas, fiscal, financeiro) e, junto dele, o
  estoque completo (aviamentos, insumos, produto acabado) — o estoque de
  tecido do Corte continua como está; a edição internacional (outros países
  nos cadastros) entra junto com os idiomas.

## Dois perfis de cliente

| Perfil | O que compra |
|---|---|
| Confecção pequena sem CAD (perfil Vaidosa) | O SmartCut completo, mais barato que Audaces + ERP |
| Confecção com ERP próprio e CAD (ex.: Audaces) | Só o módulo de corte, que lê os pedidos do ERP dela e importa o DXF que o CAD já exporta |

## Concorrentes

No Brasil, ERP e CAD vivem separados: a ligação que existe é pela ficha
técnica, não pelo chão do corte. O fluxo pedido → plano de corte automático
só aparece no topo do mercado (Gerber AccuPlan).

| Concorrente | O que faz | Preço | Relação com o SmartCut |
|---|---|---|---|
| Audaces 360 | Suíte completa: PLM, design 3D, ficha técnica, digitalização, modelagem e encaixe. Integra com ERP via ficha técnica (Audaces Idea) | Sob consulta, assinatura | Imbatível em modelagem. Não competir; importar o DXF dele |
| Molde.me | Nuvem, modular: modelagem, encaixe automático, planejador de enfestos, digitalização por foto, ficha técnica, formação de preço. Envia ao plotter | A partir de cerca de R$ 565/mês (ranking de terceiros) | Concorrente mais direto no corte. Não é ERP |
| RZ Sistemas | ERP para confecção + CAD próprio (RZ CAD Têxtil, com DigiFoto) | Não informado | Mais parecido com a visão modular do SmartCut |
| Sisplan, Systêxtil, TOTVS, Consistem | ERPs têxteis completos, implantação com consultor. Sisplan integra com Audaces | Sob consulta | Alvo do módulo de conexão, não concorrente direto |
| Gerber AccuPlan (Lectra) | Importa ordens do ERP e gera plano de enfesto e encaixe automático, considerando rolos em estoque | Alto, para grandes | Prova que a categoria "pedido → corte" tem valor |

## Diferenciais validados

Quatro funcionalidades aprovadas para entrar no SmartCut.

### 1. Desviar de defeitos no tecido

- **Dor**: furo, mancha ou falha no rolo estraga peças inteiras quando o
  encaixe passa por cima.
- **Como funciona**: o cortador marca a posição do defeito na mesa e o motor
  de encaixe refaz o plano com as peças em volta.
- **Entrada do defeito**: começar com marcação manual (clicar no encaixe na
  tela); depois, com câmera sobre a mesa, apontar direto no tecido.
- **Depende de**: motor de encaixe novo (sparrow + OR-Tools) aceitar áreas
  proibidas.

### 2. Pedidos por WhatsApp com IA

- **Dor**: muito pedido de atacado chega por mensagem ou foto de caderno e é
  redigitado à mão.
- **Como funciona**: o usuário encaminha a mensagem ou a foto; a IA lê
  cliente, produtos, cores e grade e monta um pedido em rascunho.
- **Revisão obrigatória**: o pedido abre num modal de conferência antes de
  salvar, como já é feito na importação de XML de NF-e.
- **Depende de**: cadastro de produtos e cores bem padronizado, para a IA
  casar os nomes.

### 3. Compra de tecido automática

- **Dor**: comprar tecido no olho gera falta ou sobra.
- **Como funciona**: pedidos em aberto + consumo calculado pelo encaixe +
  estoque atual de tecido = quanto comprar de cada tecido e até quando.
- **Saída**: lista de compra por fornecedor e mensagem pronta para enviar.
- **Depende de**: consumo por produto vindo do encaixe e estoque de tecido
  por lote (já existe a hierarquia Modelo → Cor → Lote).

### 4. Relatório de economia

- **Dor**: o cliente não enxerga quanto o sistema economiza, e cancela a
  assinatura.
- **Como funciona**: compara o consumo do encaixe do SmartCut com uma
  referência (encaixe manual ou histórico) e mostra kg e R$ economizados no
  mês.
- **Uso comercial**: vira argumento de venda e de renovação.
- **Depende de**: registro do consumo previsto x real por ordem de corte.

## Diferenciais já aprovados

### Integrações com plataformas

- **Fontes de pedido**: Bling e Tiny (cobrem várias lojas de uma vez),
  Nuvemshop, Shopify, Mercado Livre e ERPs de terceiros (CSV, XML ou API).
- **Sem molde na plataforma**: a loja só manda o pedido. O SmartCut mapeia
  SKU → produto → grupo de moldes e monta a grade.
- **Sem versão web**: o app instalado consulta a API das plataformas de
  tempos em tempos e puxa os pedidos novos.
- **Retorno**: devolver consumo e real cortado ao ERP do cliente.

### Projetor na mesa de corte

- **Ideia**: projetar o encaixe na mesa; o cortador risca com giz e depois
  corta. Elimina a confusão de pegar e posicionar moldes de papel.
- **Público**: microempresas que ainda cortam com molde de papel e não têm
  plotter.
- **Área**: enfestos de até 150 cm de comprimento; um projetor Full HD
  cobrindo cerca de 1,5 × 1,8 m dá perto de 1 mm por pixel.
- **Extras projetados**: nome da peça, tamanho, piques e sentido do fio.
- **Montagem**: projetor de curta distância ou fixado no teto, calibração
  pelos 4 cantos da mesa, cuidado com a luz da sala. O projetor pode vir da
  China para baixar o custo.
- **Protótipo**: abrir o SVG do encaixe em tela cheia no projetor e testar
  na mesa da Vaidosa.

### Digitalização de molde por foto

- **Ideia**: fotografar o molde de papel com o celular e gerar o molde no
  sistema.
- **Não é diferencial sozinho**: Molde.me, Audaces Digiflash, RZ DigiFoto e
  MAB Fortuna já fazem.
- **Precisão**: a distância da câmera não garante medida. Usar tapete ou
  folha com marcadores impressos de tamanho conhecido, corrigir a
  perspectiva e extrair o contorno (OpenCV).
- **Papel da IA**: achar piques, sentido do fio e ler o nome da peça.
- **Diferencial possível**: incluir no plano barato e vincular o molde
  direto ao produto cadastrado.

## Ideias em espera

Discutidas e ainda não validadas. Ficam aqui para reavaliar depois.

- **Sugestão de corte de reposição**: juntar vendas online e estoque mínimo
  por SKU e sugerir o corte da semana.
- **Câmera na mesa lendo o tecido**: medir a largura real do tecido aberto e
  ajustar o encaixe.
- **Encaixe em retalho**: a câmera lê o formato de uma sobra e o sistema
  projeta quais peças pequenas cabem nela.
- **Conferência por câmera**: verificar se todas as peças foram riscadas
  antes de cortar.
- **Kit de hardware**: vender projetor + câmera + suporte já calibrados.
- **Custo real por pedido**: consumo real vezes preço do kg, alimentando a
  Precificação.
- **Módulo de facção**: envio e retorno de lotes para costureiras
  terceirizadas e pagamento por peça.
- **Biblioteca de moldes base**: legging, top, short e macaquinho já
  graduados, para quem não tem modelista.
- **Loja de moldes**: modelistas vendem moldes digitais dentro do SmartCut,
  com comissão.
- **Molde a partir da peça pronta**: IA estimar o molde pela foto de uma
  peça esticada. Visão de longo prazo.

## Próximos passos

Ordem sugerida: primeiro o que já tem base no sistema, depois o que depende
de hardware ou integração externa. Onde cada item entra no roadmap:
[ARQUITETURA.md](ARQUITETURA.md#6-roadmap).

- [ ] Registrar consumo previsto x real por ordem de corte (base para o
      relatório de economia e a compra de tecido)
- [ ] Relatório de economia mensal
- [ ] Compra de tecido automática a partir dos pedidos em aberto
- [ ] Áreas proibidas no motor de encaixe novo (desviar de defeitos,
      marcação manual)
- [ ] Pedido por WhatsApp: leitura de texto e foto com IA + modal de revisão
- [ ] Saída HPGL para plotter
- [ ] Protótipo do projetor na mesa da Vaidosa
- [ ] Conector Bling ou Tiny (leitura de pedidos)
- [ ] Digitalização de molde por foto com marcadores impressos
- [ ] Conversar com 5 a 10 confecções e medir o tempo do pedido até o risco
      pronto (e quantas pessoas usam o corte ao mesmo tempo — decide se
      PostgreSQL e modo servidor sobem na fila)
