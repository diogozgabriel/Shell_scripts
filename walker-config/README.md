# Walker — tema "grid-wide"

Tema para o [Walker](https://github.com/abenz1267/walker) (launcher de
aplicativos para Wayland) que alarga a janela, a lista de resultados e o
painel de preview, para que ícones/textos/caminhos parem de ser cortados.

Testado nesta máquina com Walker 2.16.2 e o tema base `grid` (padrão do
KooLDots/Garuda). É uma cópia completa do tema `grid` com os seguintes
ajustes:

- `layout.xml`: janela de 900x570 → 1600x680; lista (`Scroll`) de 840px →
  1000px de largura, 400px → 450px de altura.
- `preview.xml`: painel de preview de 500x300 → 550x450.
- `style.css`: `min-width` do preview reforçado via CSS + `item-subtext`
  ligeiramente maior (12px → 13px) para melhor leitura.

O tema `grid` usa **classes CSS** (`.item-box`, `.preview`, `.scroll`...)
definidas via `layout.xml`/`preview.xml`, não IDs (`#sidebar`, `#providerlist`
etc. não existem nesse tema) — por isso a única forma confiável de alargar os
painéis é copiar o tema inteiro e editar os `width-request`/`min-content-width`
nos XML, não só sobrepor uma folha de estilo com `theme_base`.

## Instalação

1. Copie a pasta do tema para o seu `~/.config/walker/themes/`:

   ```bash
   cp -r walker-config/themes/grid-wide ~/.config/walker/themes/
   ```

2. No seu `~/.config/walker/config.toml`, troque a linha do tema:

   ```toml
   theme = "grid-wide"
   ```

3. Reinicie o serviço do Walker para carregar o tema do zero:

   ```bash
   systemctl --user restart walker.service
   ```

## Se você usa outro tema (não o `grid`)

Copie a pasta do seu tema atual em vez da `grid-wide` daqui, e repita os
ajustes de largura acima nos arquivos correspondentes. Para achar os nomes
reais dos widgets/classes do seu tema, abra o Walker com o inspector do GTK:

```bash
GTK_DEBUG=interactive walker
```
