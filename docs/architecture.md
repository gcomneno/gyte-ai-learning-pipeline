# Architettura iniziale

## Confini

### GYTE

Fornisce i mattoni generali per ottenere e preparare il testo:

- `gyte-transcript`
- `gyte-reflow-text`

### GYTE Study Tools

Orchestra il workflow didattico ed editoriale:

- identificazione del video;
- creazione della directory di lavoro;
- selezione delle caption;
- fallback di trascrizione;
- normalizzazione;
- validazione;
- creazione del pacchetto di analisi;
- generazione della Lesson Learned;
- conversione Markdown → PDF;
- conversione Markdown → EPUB;
- validazione degli output.

### Materiali privati

Sono conservati esternamente al repository:

```text
/home/baltimora/Progetti/labs/gyte-study-private-material
```

## Fasi previste

1. `inspect`
   - recupero metadati;
   - verifica caption;
   - creazione di uno slug stabile.

2. `transcribe`
   - priorità a `it-orig`;
   - fallback a `it`;
   - fallback futuro a Whisper.

3. `prepare`
   - conservazione del transcript originale;
   - normalizzazione UTF-8 e HTML;
   - reflow AI-friendly;
   - controllo del conteggio delle parole;
   - generazione di `transcript.analysis.md`.

4. `compose`
   - versione assistita: attende la Lesson Learned revisionata;
   - versione completa futura: usa un provider LLM configurabile.

5. `publish`
   - sorgente unica Markdown;
   - generazione indipendente di PDF ed EPUB;
   - metadati coerenti;
   - backup degli output precedenti.

6. `validate`
   - integrità ZIP dell'EPUB;
   - verifica del mimetype;
   - controllo del testo recuperabile;
   - riepilogo finale.

## Stato riavviabile

Ogni fase dovrà produrre un file di stato o output riconoscibile.

Una nuova esecuzione non dovrà ripetere automaticamente una fase già valida,
salvo richiesta esplicita con opzioni come:

```text
--force
--from prepare
--rebuild epub
```

## Dipendenze

La versione iniziale usa esclusivamente:

- libreria standard Python;
- comandi GYTE;
- `yt-dlp`;
- Calibre;
- Poppler.

Non richiede Pandoc, WeasyPrint o wkhtmltopdf.
