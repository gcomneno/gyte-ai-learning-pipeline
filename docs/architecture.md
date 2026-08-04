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

## Implementazione corrente

La fase `inspect` è disponibile e:

- interroga `yt-dlp` senza scaricare contenuti multimediali;
- raccoglie metadati e lingue delle caption;
- preferisce `it-orig`, poi `it`;
- distingue caption manuali e automatiche;
- crea un workspace privato stabile;
- registra lo stato della fase in forma JSON.

### Fase prepare

La fase `prepare`:

- riutilizza un transcript caption già presente;
- invoca `gyte-transcript` solo quando necessario;
- conserva una copia stabile del testo originale;
- normalizza le entità HTML;
- esegue il reflow AI-friendly;
- verifica che il reflow non perda parole;
- genera il Markdown da caricare per la revisione editoriale;
- adotta senza riscriverli output completi già esistenti;
- registra le fasi `transcribe` e `prepare` nel file di stato.

### Fase publish

La fase `publish`:

- accetta una Lesson Learned revisionata in Markdown;
- ricava il titolo dall'H1;
- normalizza il titolo Kindle;
- renderizza HTML semantico senza dipendenze Python esterne;
- genera PDF ed EPUB separatamente tramite Calibre;
- valida struttura EPUB e testo recuperabile;
- valida il testo recuperabile dal PDF;
- conserva gli output precedenti con backup timestampati;
- genera un manifest con hash SHA-256;
- registra la pubblicazione nello stato della pipeline.

### Ingresso article

Gli URL HTTP non riconosciuti come YouTube seguono una pipeline distinta:

1. download HTML con user agent dichiarato;
2. lettura dei metadati Open Graph e JSON-LD;
3. estrazione del contenitore `post-body` o `entry-content`;
4. esclusione del boilerplate della pagina;
5. registrazione separata dei riferimenti scientifici;
6. produzione di `article.analysis.md`;
7. successiva revisione editoriale e pubblicazione condivisa.
