# GYTE Study Tools

Companion project di [GYTE](https://github.com/gyte/gyte) per trasformare
video e transcript in materiali didattici personali e formati adatti alla
lettura su Kindle.

## Obiettivo

Fornire un comando unico:

```text
gyte-lesson-kindle URL_YOUTUBE
```

La pipeline prevista è:

```text
YouTube
  → metadati
  → caption o trascrizione
  → normalizzazione
  → reflow
  → transcript di analisi
  → Lesson Learned
  → PDF ed EPUB
  → validazione
```

## Stato

Fondazione iniziale. La pipeline editoriale non è ancora implementata.

La prima versione sarà assistita:

1. automatizza tutte le fasi deterministiche;
2. prepara `transcript.analysis.md`;
3. lascia la revisione e la generazione della Lesson Learned a un passaggio
   editoriale controllato;
4. genera PDF ed EPUB dalla stessa sorgente Markdown finale.

## Responsabilità

Questo progetto:

- orchestra gli strumenti GYTE;
- gestisce cartelle, metadati e stato della pipeline;
- valida transcript e output;
- conserva prompt e template;
- genera formati di lettura.

GYTE continua a occuparsi di:

- estrazione delle caption;
- pulizia del transcript;
- reflow del testo.

## Materiali privati

Transcript, materiali derivati e output editoriali non devono essere
salvati nel repository.

Directory privata predefinita:

```text
/home/baltimora/Progetti/labs/gyte-study-private-material
```

## Prerequisiti locali

- Python 3
- `gyte-transcript`
- `gyte-reflow-text`
- `yt-dlp`
- Calibre:
  - `ebook-convert`
  - `ebook-meta`
- `pdftotext`

## Controllo ambiente

```bash
bin/gyte-lesson-kindle --check
```

## Installazione locale prevista

```bash
scripts/install-local.sh
```

L'installer crea il collegamento:

```text
~/.local/bin/gyte-lesson-kindle
```

## Principi

- pipeline riavviabile;
- nessuna sovrascrittura silenziosa;
- materiali privati separati dal codice;
- output riproducibili;
- passaggi verificabili;
- degrado controllato da caption a Whisper;
- nessuna dipendenza obbligatoria da servizi AI nella versione assistita.
