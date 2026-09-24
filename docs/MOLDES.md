# MOLDES.md — Especificação do Módulo de Moldes

## Visão geral

O módulo de Moldes é o coração técnico do SmartCut. É onde os arquivos de molde
(PLT/DXF/ADS) são importados, visualizados, editados e preparados para o encaixe.

O objetivo é ter funcionalidades comparáveis ao Audaces Encaixe Especialista
nas funções essenciais, com uma interface mais simples e integrada ao restante do sistema.

---

## Estado atual (Junho 2026)

### O que funciona
- Importação de arquivos PLT, DXF e ADS
- Conversão para SVG e exibição no browser
- Organização em Grupos de Molde com código de referência
- Graduação P, M, G, GG
- Sentido do fio: linha arrastável com ângulo salvo em graus
- Flip horizontal e flip vertical

### Problemas conhecidos
- SVG gerado pode vir desalinhado (rotacionado ou fora do canvas)
- Piques nem sempre são detectados na importação
- Sem margem de costura
- Sem suporte a tecido tubular
- Canvas sem zoom/pan para moldes grandes

---

## Melhorias planejadas (Fase 3C)

### 1. Leitura e visualização correta

**Problema:** Ao importar um PLT, o molde pode aparecer em qualquer orientação,
forçando o usuário a rotacionar manualmente.

**Solução:**
- Após converter para SVG, calcular o bounding box do molde
- Detectar se o eixo maior é horizontal ou vertical
- Se horizontal: rotacionar 90° para deixar vertical (posição de uso)
- Centralizar no canvas automaticamente
- Normalizar escala para caber no viewport com padding

**Canvas:**
- Zoom com scroll do mouse (50% a 400%)
- Pan com clique e arraste no fundo
- Régua em cm nas bordas (horizontal e vertical)
- Grade opcional (toggle)

---

### 2. Piques (entalhes de encaixe)

**O que são:** Pequenos cortes em V ou I nas bordas do molde que servem de
referência para o costureiro encaixar peças. São críticos para a costura correta.

**Detecção automática:**
- Ao parsear o PLT: identificar segmentos muito curtos (< 5mm) perpendiculares à borda
- Marcar como pique e salvar coordenadas separadas na tabela de moldes
- Exibir no SVG como triângulos pequenos na borda (cor diferente)

**Edição manual:**
- Ferramenta "Adicionar pique": clicar na borda do molde para inserir
- Ferramenta "Remover pique": clicar em pique existente para deletar
- Piques aparecem no PDF de corte como marcações

---

### 3. Margem de costura

**O que é:** Espaço adicionado ao redor do molde para a costura.
Exemplo: molde tem 38cm de busto → com margem de 1cm → peça cortada tem 40cm de busto.

**Implementação:**
- Campo "Margem de costura" por molde (float, em cm, default 1.0)
- Opção: margem uniforme ou por lado (superior/inferior/lateral)
- Visualização: linha tracejada ao redor do contorno original
- Toggle "Mostrar margem" no canvas
- No encaixe: usar as dimensões COM margem para cálculo de aproveitamento
- No PDF: imprimir o contorno COM margem (é o que o cortador segue)

---

### 4. Tecido tubular (dobrado)

**O que é:** Muitos tecidos de malha vêm dobrados ao meio no rolo.
A largura real é o dobro da largura visível.
O molde é espelhado na dobra, então você encaixa apenas metade da peça.

**Implementação:**
- Checkbox "Tecido tubular" por encaixe
- Quando ativado: desenhar linha de dobra vertical no centro do canvas
- Moldes são posicionados apenas no lado esquerdo (metade)
- Visualização mostra o espelho automaticamente no lado direito (mais claro, indicativo)
- Cálculo de consumo: `consumo = comprimento_encaixe` (não dobra a largura)
- PDF de corte: indica "TECIDO TUBULAR — cortar na dobra"

---

### 5. Ferramentas de posicionamento

Inspiradas no Audaces, adaptadas para o SmartCut:

| Ferramenta | Atalho | Descrição |
|---|---|---|
| Alinhar à esquerda | — | Move molde para borda esquerda do canvas |
| Alinhar à direita | — | Move molde para borda direita |
| Centralizar | — | Centraliza horizontalmente |
| Rotacionar 90° | R | Rotaciona em 90° graus |
| Rotacionar livre | — | Campo de input com graus |
| Espelhar horizontal | H | Flip no eixo Y |
| Espelhar vertical | V | Flip no eixo X |
| Snap to grid | G | Ativa grade de encaixe |
| Distribuir | — | Distribui espaçamento uniforme entre moldes selecionados |

---

### 6. Grupos por tamanho (Pacotes)

**O que são:** No Audaces, "pacotes" são os grupos de moldes por tamanho.
Ajudam o cortador a saber quais peças pertencem a qual tamanho.

**Implementação:**
- Cada tamanho (P/M/G/GG/G1/G2/G3) recebe uma cor de borda no canvas
- Legenda de cores exibida no canto inferior direito do canvas
- Toggle individual: clicar na legenda para mostrar/ocultar um tamanho
- No PDF de corte: cada tamanho é impresso com hachura diferente ou legenda

**Paleta de cores por tamanho:**
```
P  → cinza escuro
M  → cinza médio
G  → preto
GG → grafite
G1 → neutro quente 1
G2 → neutro quente 2
G3 → neutro quente 3
```
(Sem azul — usar escala de neutros + variações da cor principal do sistema)

---

### 7. Fila de encaixe

**O que é:** Em vez de encaixar um pedido por vez, você monta uma fila
de pedidos e o sistema processa todos em sequência.

**Fluxo:**
1. Tela "Fila de Encaixe": lista de pedidos aguardando
2. Usuário adiciona pedidos à fila e define tecido para cada um
3. Botão "Processar fila": encaixa um por um
4. Relatório ao final: consumo total de tecido, aproveitamento médio, tempo estimado de corte

**Utilidade para Vaidosa Fitness:**
Quando chegam múltiplos pedidos de representantes ao mesmo tempo,
processar a fila evita fazer um encaixe por vez e permite planejar o corte do dia.

---

### 8. Ordem de corte

**O que é:** Numeração das peças na sequência que o cortador deve cortar.
Evita movimentos desnecessários e garante consistência.

**Algoritmo sugerido:**
- Varrer o encaixe da esquerda para a direita
- Dentro de cada coluna: de cima para baixo
- Numerar as peças nessa ordem

**Exibição:**
- Número exibido no centro de cada peça no canvas
- Toggle "Mostrar ordem de corte"
- PDF de corte inclui os números

**Edição:**
- Arrastar para reordenar na lista lateral
- Canvas atualiza numeração em tempo real

---

## Tabela de moldes — campos completos (após Fase 3C)

```sql
moldes (
  id                    SERIAL PRIMARY KEY,
  grupo_id              INT REFERENCES grupos_molde(id),
  nome                  VARCHAR,
  tamanho               VARCHAR,        -- P, M, G, GG, G1, G2, G3
  arquivo_original_path VARCHAR,        -- caminho do PLT/DXF/ADS original
  svg_path              VARCHAR,        -- SVG processado
  area_cm2              FLOAT,
  perimetro_cm          FLOAT,
  largura_cm            FLOAT,          -- bounding box largura
  altura_cm             FLOAT,          -- bounding box altura
  sentido_fio_graus     FLOAT,
  flip_horizontal       BOOLEAN,
  flip_vertical         BOOLEAN,
  margem_costura_cm     FLOAT DEFAULT 1.0,
  tem_piques            BOOLEAN DEFAULT FALSE,
  piques_json           TEXT,           -- JSON com coordenadas dos piques
  created_at            TIMESTAMP
)
```
