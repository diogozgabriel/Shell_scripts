# Walker — tema "wide-sidebar"

Override de tema para o [Walker](https://github.com/abenz1267/walker) (launcher
de aplicativos para Wayland) que alarga os painéis laterais (lista de
resultados / lista de providers) para que ícones e textos parem de ser
cortados.

Este repositório **não** roda o Walker (é um container isolado sem acesso à
sua máquina), então os valores abaixo são um ponto de partida — ajuste os
`min-width` conforme sua tela e o tema que você já usa.

## Instalação

1. Copie a pasta do tema para o seu `~/.config/walker/themes/`:

   ```bash
   cp -r walker-config/themes/wide-sidebar ~/.config/walker/themes/
   ```

2. No seu `~/.config/walker/config.toml`, adicione o tema como uma camada
   *depois* do seu tema atual, para que só os `min-width` sejam
   sobrescritos (deixando o resto do visual como está):

   ```toml
   [theme]
   theme_base = ["default", "wide-sidebar"]
   ```

   Se a sua versão do Walker usa `theme = "nome"` (uma string só, sem lista),
   copie o `.toml` de layout do seu tema atual para
   `wide-sidebar/wide-sidebar.toml` (sem mudar nada nele) e cole as regras de
   `wide-sidebar.css` dentro do `.css` do seu tema atual.

3. Reinicie o Walker (ou o daemon, se estiver rodando em background).

## Ajustando os valores

Os seletores CSS (`#list`, `#sidebar`, `#preview`, etc.) podem variar entre
versões do Walker. Se algum não fizer efeito, abra o Walker com o inspector
do GTK para conferir os nomes reais dos widgets na sua instalação:

```bash
GTK_DEBUG=interactive walker
```

Aumente/diminua os valores de `min-width` em `wide-sidebar.css` até o texto
parar de ser cortado.
