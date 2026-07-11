# Busca de Arquivos (file_search_app)

Ferramenta desktop de busca local de arquivos por **nome** e por **conteúdo
textual**, no espírito do Recoll/Catfish, feita para o Garuda Linux (funciona
em qualquer Linux, com suporte também a Windows e macOS).

Todo o processamento é **100% local**: nenhum nome, caminho ou conteúdo de
arquivo sai da máquina; não há chamadas a APIs externas de OCR ou indexação.

## 1. Resumo da arquitetura

```
GUI (PySide6)  ──►  IndexScheduler (QThread + QTimer)  ──►  Indexer (puro Python)
     │                                                          │
     │  QThreadPool                                             ▼
     └─►  SearchService  ◄──────────  SQLite (WAL) + FTS5  ◄──  Extractors
```

- **GUI** (`app/gui/`): janela principal com busca *debounced* (300 ms),
  filtros, tabela de resultados (`QAbstractTableModel`), menu de contexto e
  diálogo de configurações. Nunca executa I/O pesado: buscas rodam em um
  `QThreadPool` (resultados obsoletos são descartados por id de requisição) e
  a indexação em uma `QThread` própria.
- **Indexação** (`app/indexing/`): `Indexer` é independente de Qt (testável
  em CI sem display); `IndexScheduler` o envolve com sinais Qt, impede
  execuções simultâneas, oferece cancelamento cooperativo
  (`threading.Event`) e dispara a atualização automática via `QTimer`.
- **Extratores** (`app/indexing/extractors/`): um por família de formato,
  registrados por extensão em `build_registry()`. Dependências pesadas
  (PyMuPDF, python-docx, openpyxl, pytesseract) são importadas de forma
  tolerante — se ausentes, o formato é indexado só por metadados.
- **Banco** (`app/database/`): SQLite em WAL com tabela `files` + tabela
  virtual FTS5 *external content* sincronizada por triggers, tabela
  `settings` e versão de esquema via `PRAGMA user_version` com migrações.
- **Busca** (`app/search/`): combina `LIKE` (nome/caminho, subpalavras) com
  FTS5 (conteúdo, prefixos, bm25, `snippet()`), com filtros parametrizados.
- **Serviços** (`app/services/`): configurações persistidas em JSON na
  tabela `settings`; ações de gerenciador de arquivos por SO.

## 2. Decisões técnicas e limitações

| Decisão | Justificativa |
|---|---|
| FTS5 *external content* + triggers | O FTS nunca diverge da tabela principal, mesmo com UPDATE/DELETE diretos. |
| Tokens FTS entre aspas + `*` | Neutraliza operadores da sintaxe FTS5 vindos do usuário e dá correspondência por prefixo. |
| `LIKE` para nome/caminho | FTS5 só casa prefixos de token; `LIKE %termo%` cobre subpalavras em qualquer posição (ex.: `relat` em `meu_relatorio`). |
| `remove_diacritics 2` no tokenizer | “fuba” encontra “fubá” — essencial em português. |
| Indexer sem Qt | Testes rodam sem display/PySide6; a GUI é só um invólucro. |
| Uma conexão SQLite por thread + WAL | Conexões SQLite não podem cruzar threads; WAL permite buscar durante a indexação. |
| Detecção de mudança por (mtime, tamanho) | Barato (um `stat` por arquivo); hash seria caro. Limitação: alterações que preservam mtime e tamanho não são detectadas. |
| Conteúdo truncado em 1 MI de caracteres | Limita o crescimento do banco e o uso de memória. |
| `os.walk(followlinks=False)` | Evita ciclos de links simbólicos; links para fora das pastas não são seguidos (limitação assumida). |
| OCR desativado por padrão | OCR é ordens de magnitude mais lento que extração nativa. |

Outras limitações: sem *watch* de sistema de arquivos (inotify) — a
atualização é periódica; PDFs cifrados e DOC/XLS legados (binários) ficam só
com metadados; a relevância intercala “nome primeiro, depois bm25”, sem
ranqueamento unificado.

## 3. Estrutura de diretórios

```
file_search_app/
├── main.py                       # ponto de entrada
├── requirements.txt
├── README.md
├── app/
│   ├── gui/
│   │   ├── main_window.py        # janela principal, busca, resultados
│   │   ├── settings_dialog.py    # pastas, exclusões, auto-update, OCR
│   │   └── models.py             # modelo Qt da tabela de resultados
│   ├── indexing/
│   │   ├── indexer.py            # varredura incremental (sem Qt)
│   │   ├── scheduler.py          # QThread + QTimer + cancelamento
│   │   └── extractors/
│   │       ├── base.py           # contrato + limite de conteúdo
│   │       ├── text_extractor.py # TXT/MD/CSV/JSON/XML + HTML
│   │       ├── pdf_extractor.py  # PyMuPDF + OCR de páginas digitalizadas
│   │       ├── office_extractor.py  # DOCX (python-docx), XLSX (openpyxl)
│   │       └── image_ocr_extractor.py  # OCR de imagens + utilidades Tesseract
│   ├── database/
│   │   ├── connection.py         # fábrica de conexões, WAL, checagem FTS5
│   │   ├── schema.py             # esquema, versão e migrações
│   │   └── repository.py         # consultas parametrizadas
│   ├── search/
│   │   └── search_service.py     # LIKE + FTS5, filtros, snippets
│   ├── services/
│   │   ├── file_manager.py       # copiar caminho, abrir/revelar pasta
│   │   └── settings_service.py   # AppConfig ⇄ JSON na tabela settings
│   └── utils/
│       ├── logging_config.py
│       └── platform_utils.py     # xdg-open / Explorer / Finder, dirs de dados
└── tests/                        # pytest, sem dependência de Qt
```

## 4. Instalação

Requisitos: Python 3.11+ (3.12+ recomendado) com SQLite compilado com FTS5
(padrão nas distribuições atuais).

```bash
cd file_search_app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No Garuda/Arch, as dependências de sistema do Qt já estão presentes em
instalações desktop. Em servidores/containers: `sudo pacman -S qt6-base`.

## 5. Instalação do Tesseract (apenas se for usar OCR)

- **Garuda / Arch / Manjaro**
  ```bash
  sudo pacman -S tesseract tesseract-data-por tesseract-data-eng
  ```
- **Debian / Ubuntu**
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
  ```
- **Fedora**
  ```bash
  sudo dnf install tesseract tesseract-langpack-por
  ```
- **Windows**: instalador da UB Mannheim em
  <https://github.com/UB-Mannheim/tesseract/wiki>; marque os idiomas
  desejados e adicione a pasta de instalação ao `PATH`.
- **macOS**
  ```bash
  brew install tesseract tesseract-lang
  ```

O aplicativo detecta a ausência do Tesseract e mostra essas instruções ao
ativar o OCR; a indexação continua funcionando sem ele (imagens ficam só com
metadados).

## 6. Execução

```bash
cd file_search_app
source .venv/bin/activate
python main.py
```

Primeiro uso: clique em **“Pastas…”**, adicione as pastas a indexar (a caixa
de seleção de cada pasta controla a recursividade) e confirme — a primeira
indexação inicia automaticamente. Banco, configurações e logs ficam em
`~/.local/share/file-search-app/` (ou equivalente no Windows/macOS).

## 7. Como o índice incremental funciona

1. No início de cada execução, o indexador carrega em memória o mapa
   `caminho → (tamanho, mtime)` de todo o índice (uma única consulta).
2. Para cada arquivo encontrado na varredura (`os.walk`, sem seguir
   symlinks, podando pastas ocultas/excluídas), faz um `stat`:
   - **não está no mapa** → arquivo novo: extrai conteúdo e insere;
   - **tamanho e mtime iguais** → inalterado: pula (custo de um `stat`);
   - **diferentes** → modificado: reextrai e atualiza (o trigger FTS5
     substitui o conteúdo pesquisável).
3. Ao final, todo caminho do mapa que **não foi visto** na varredura e está
   sob uma raiz varrida com sucesso (ou fora de qualquer raiz configurada) é
   removido — arquivos apagados e pastas desconfiguradas saem do índice.
   Raízes inacessíveis nesta execução são preservadas para evitar perda de
   índice por um disco desmontado.
4. Erros por arquivo (permissão, corrupção, falha de OCR) são gravados nos
   campos `status`/`error` do registro e não interrompem a varredura.
5. O `IndexScheduler` repete o processo a cada N minutos (padrão 20) e
   bloqueia execuções simultâneas.

## 8. Como adicionar suporte a um novo formato

1. Crie um extrator em `app/indexing/extractors/`, subclasse de
   `BaseExtractor`, declarando as extensões e implementando `extract()`:

   ```python
   from app.indexing.extractors.base import BaseExtractor, ExtractionResult

   class EpubExtractor(BaseExtractor):
       extensions = ("epub",)

       def extract(self, path, config):
           try:
               text = ...  # extraia o texto aqui
               return ExtractionResult(text=text).truncated()
           except Exception as exc:
               return ExtractionResult(status="error", error=str(exc))
   ```

2. Registre a classe na lista de `build_registry()` em
   `app/indexing/extractors/__init__.py`.
3. Se houver dependência externa, importe-a em `try/except ImportError` e
   retorne `status="metadata_only"` quando ausente (veja `pdf_extractor.py`).

Nenhuma outra parte do código precisa mudar.

## 9. Testes

```bash
pip install pytest
python -m pytest tests/ -v
```

Os testes não dependem de PySide6 nem de display; cobrem criação do banco e
versão do esquema, sincronia do FTS em update/delete, inclusão/atualização/
remoção incremental, exclusões padrão, arquivos grandes, corrompidos e sem
permissão de leitura, normalização/sanitização de consultas, busca por nome,
conteúdo, múltiplas palavras e filtros, e extração de texto (UTF-8, Latin-1,
HTML).

## 10. Possíveis melhorias futuras

- Monitoramento em tempo real com inotify/watchdog em vez de varredura
  periódica.
- Ranqueamento unificado (nome + conteúdo) e realce em rich text na tabela.
- Suporte a EPUB, ODT/ODS, RTF e e-mails (mbox/eml).
- Pré-visualização do arquivo no painel lateral.
- Ícone na bandeja do sistema com indexação em segundo plano.
- Empacotamento (PKGBUILD para o Garuda/AUR, Flatpak).
- Paralelizar a extração (processos) mantendo a escrita serializada.
- Detecção de idioma por documento para OCR automático.
