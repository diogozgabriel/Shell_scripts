# AI Chat Hub

App desktop (Electron) que reúne vários chats de IA em uma só janela, com **login
web** em cada serviço — sem precisar de chave de API.

Serviços incluídos por padrão: **Claude, ChatGPT, Gemini, Deepseek, innerAI,
Copilot e Perplexity**. Você pode adicionar, remover, reordenar e editar
qualquer serviço.

## Instalação no Garuda Linux (Arch)

**Opção 1 — pacote pacman (recomendado):**

```bash
sudo pacman -U ai-chat-hub-1.0.0.pacman
```

O app aparece no menu como "AI Chat Hub".

**Opção 2 — AppImage (sem instalar):**

```bash
chmod +x "AI Chat Hub-1.0.0.AppImage"
./"AI Chat Hub-1.0.0.AppImage"
```

## Login com Google

O app se identifica como um Chrome comum e abre os popups de OAuth dentro da
própria janela, na mesma sessão do serviço — por isso o login com Google
**funciona normalmente** na maioria dos casos. Se algum serviço ainda recusar,
use o login por e-mail/senha desse serviço como alternativa.

Cada serviço tem a sua própria sessão isolada e persistente: você loga uma vez
e o login fica salvo entre reinicializações. Para deslogar de um serviço, use
**Configurações → Serviços → Sair**.

## Configurações (⚙ ou `Ctrl+,`)

- **Tema** claro/escuro e **barra lateral compacta** (só ícones)
- **Zoom** dos chats (também `Ctrl+=` / `Ctrl+-`)
- **Enter envia a mensagem** (padrão ligado). Desligado, Enter cria nova linha
- **Correção ortográfica** pt-BR/en-US com sugestões no clique direito
- **Links externos** abrem no navegador padrão (configurável)
- **Serviço inicial** ao abrir o app
- **User-Agent personalizado**, se algum dia precisar trocar
- **Serviços**: adicionar qualquer site de chat, renomear, trocar ícone (emoji),
  URL, ativar/desativar, reordenar e apagar sessão/login

As configurações ficam em `~/.config/ai-chat-hub/config.json` (editável à mão).

## Atalhos

| Atalho | Ação |
|---|---|
| `Enter` | Envia a mensagem |
| `Shift+Enter` | Nova linha |
| `Ctrl+1` … `Ctrl+9` | Troca de serviço |
| `Ctrl+R` | Recarrega o serviço atual |
| `Ctrl+,` | Configurações |
| `Ctrl+=` / `Ctrl+-` | Zoom |

## Compilar a partir do código

```bash
cd ai-chat-hub
npm install
npm start            # roda em modo desenvolvimento
npm run dist:linux   # gera .pacman e .AppImage em dist/
```
