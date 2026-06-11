# Garuda Toolbox

Três ferramentas do dia a dia em um só app, feito para o Garuda Linux:

| Aba | O que faz |
|---|---|
| 📸 **Print → Texto** | Captura uma área da tela e extrai o texto (OCR pt-BR/inglês). Botão para copiar e abrir o AI Chat Hub com o texto pronto para colar. |
| 🎬 **Conversor** | Arraste vídeo, áudio ou imagem e converta para outro formato (MP4, MKV, WebM, GIF, MP3, FLAC, PNG, WebP, AVIF…), com barra de progresso. |
| ⬇️ **Baixador** | Cole um link (YouTube e centenas de sites), escolha a qualidade ou só o áudio em MP3, e baixe com progresso e fila. |

## Instalação

```bash
sudo pacman -U garuda-toolbox-1.0.0.pacman
```

O app usa ferramentas que o Garuda normalmente já tem. Se faltar alguma, o
próprio app avisa e mostra o comando, mas você pode garantir tudo com:

```bash
sudo pacman -S --needed tesseract tesseract-data-por tesseract-data-eng \
                        ffmpeg imagemagick yt-dlp spectacle
```

## OCR de qualquer lugar (atalho global)

No KDE: **Configurações do Sistema → Atalhos → Adicionar comando** e use:

```
garuda-toolbox --ocr
```

Atribua uma tecla (ex.: `Meta+T`). Ao pressionar, você seleciona a área da
tela e o texto reconhecido aparece no app.

## Compilar a partir do código

```bash
cd garuda-toolbox
npm install
npm run dist:linux   # gera o .pacman em dist/
```
