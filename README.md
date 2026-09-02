# Simulador de Terremoto — Protótipo (PyOpenGL)

Protótipo simples e organizado de um simulador de terremoto: uma "cidade"
de prédios em cima de um chão em grade, onde uma onda sísmica se propaga
a partir de um epicentro e faz tudo balançar.

## Como rodar

```bash
pip install pygame PyOpenGL PyOpenGL_accelerate
python main.py
```

**Controles:**
- `ESPAÇO` → dispara um terremoto em um epicentro aleatório
- `ESC` → sai

## Estrutura do projeto

```
earthquake_sim/
├── main.py         # ponto de entrada: janela, loop principal, eventos
├── earthquake.py   # física da onda sísmica (sem nenhuma linha de OpenGL)
├── scene.py        # objetos visuais: Ground (chão) e Building (prédios)
├── camera.py        # câmera simples que orbita a cena
└── README.md
```

A ideia de separar assim: **`earthquake.py` não sabe que existe uma
tela** — ele só calcula deslocamento (dx, dy, dz) para qualquer ponto
(x, z) em qualquer instante de tempo. Isso facilita testar a física
sozinha (dá pra rodar em um script sem abrir janela nenhuma, como fizemos
para validar) e facilita trocar a forma de desenhar sem mexer na
simulação.

## Como a simulação funciona

- `EarthquakeSimulator` guarda um epicentro `(x, z)`, um instante de
  início, e parâmetros de magnitude/frequência/decaimento.
- `get_offset(x, z, tempo)` calcula:
  1. a distância do ponto até o epicentro;
  2. quanto tempo a "frente de onda" leva pra chegar até lá
     (`distância / velocidade`);
  3. a amplitude da vibração naquele ponto e instante, decaindo tanto
     no tempo (quanto mais tempo passou, mais fraco) quanto no espaço
     (quanto mais longe do epicentro, mais fraco).
- `Ground` usa esse deslocamento para ondular a grade do chão.
- `Building` usa o mesmo deslocamento, mas desenha o prédio em fatias
  horizontais e multiplica o deslocamento pela altura da fatia — assim
  o topo do prédio balança mais que a base (efeito "chicote"), que é o
  comportamento visualmente mais reconhecível de um terremoto.

## Sugestões de próximos passos para o grupo

Em ordem de dificuldade crescente:

1. **Painel de controle simples** — trocar `ESPAÇO` fixo por teclas que
   ajustam `magnitude`, `frequency` e `wave_speed` em tempo real, para
   comparar terremotos fracos vs. fortes.
2. **Clique para escolher o epicentro** — usar `pygame.mouse` +
   `gluUnProject` para converter o clique do mouse em uma posição no
   chão, em vez de sortear aleatoriamente.
3. **Câmera controlável** — trocar `OrbitCamera` (que gira sozinha) por
   uma câmera livre (WASD + mouse look), útil pra "andar" pela cidade
   durante o tremor.
4. **Colapso de prédios** — quando a amplitude acumulada em um prédio
   passar de um limite, trocar sua cor pra vermelho e, com mais tempo
   disponível, simular queda (interpolar a altura até zero).
5. **Texturas e iluminação** — hoje os objetos são cor sólida via
   `glColor3f`; dá pra evoluir para luz direcional (`GL_LIGHTING`) e
   texturas simples (concreto/vidro) sem mudar a estrutura do projeto.
6. **Sismógrafo na tela** — um HUD 2D simples (desenhado por cima da
   cena 3D) mostrando a amplitude no ponto onde a câmera está olhando,
   como um gráfico em tempo real.

Cada um desses pode virar um arquivo novo (`hud.py`, `controls.py`,
etc.) sem precisar reescrever o que já existe — essa é a vantagem de já
começar organizado.
