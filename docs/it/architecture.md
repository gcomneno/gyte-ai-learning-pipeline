# Architettura iniziale

[English](../architecture.md) | [Italiano](architecture.md)

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
- pubblicazione della lezione sorgente revisionata;
- conversione Markdown → PDF;
- conversione Markdown → EPUB;
- validazione degli output.

### Materiali privati

Sono conservati esternamente al repository.

Directory predefinita:

```text
~/.local/share/gyte-study-private-material
```

Il percorso può essere sostituito tramite `--work-root` o
`GYTE_STUDY_WORK_ROOT`.

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
   - versione assistita: attende la lezione sorgente revisionata;
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

7. `delivery`
   - transizione locale **prepare** solo dopo `publish` completo e manifest
     valido;
   - verifica di hash e dimensione EPUB, quindi copia indipendente atomica in
     `delivery/outbox/` (mai hard link);
   - richiesta `kindle-delivery-request.json` con stato `pending`,
     `handoff_mode=external-file-transfer` e
     `handoff_status=awaiting-transfer`;
   - trasferimento/upload dell'allegato locale nell'ambiente accessibile al
     Gmail connector, poi invio esterno;
   - transizione locale **record receipt** che salva la ricevuta e aggiorna
     lo stato a `complete` con `handoff_status=connector-sent`.

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

- accetta una lezione sorgente revisionata in Markdown;
- ricava il titolo dall'H1;
- conserva il titolo H1 senza aggiungere etichette;
- renderizza HTML semantico senza dipendenze Python esterne;
- genera PDF ed EPUB separatamente tramite Calibre;
- valida struttura EPUB e testo recuperabile;
- valida il testo recuperabile dal PDF;
- conserva gli output precedenti con backup timestampati;
- genera un manifest con hash SHA-256;
- registra la pubblicazione nello stato della pipeline.

### Fase delivery

La consegna Kindle mantiene esplicito il confine tra filesystem privato e
connector esterno. `--kindle-email` può essere usato insieme a
`--publish-from`: non invia email, ma prepara una richiesta verificabile
contenente destinatario, oggetto, hash, dimensione e percorso dell'EPUB.
Il flusso è `prepare locale -> transfer/upload attachment -> Gmail connector
send -> local receipt`. Il percorso dell'outbox è locale al workspace e non è
automaticamente leggibile dal connector: `attachment_path` può essere usato
direttamente solo con filesystem condiviso; altrimenti utente o orchestratore
devono trasferire il file. SHA-256 e dimensione identificano l'artefatto da
trasferire. Il connector Gmail restituisce una ricevuta dell'invio Gmail.
`--record-kindle-delivery RECEIPT URL` risolve il workspace dai metadati
locali e registra tale ricevuta in modo atomico. Non esistono OAuth, SMTP,
token o configurazioni Gmail nel repository.

L'EPUB nell'outbox è sempre una copia con inode distinto dall'artefatto
pubblicato: le due versioni non condividono contenuto modificabile. Prima di
registrare una ricevuta, il contratto JSON, il percorso confinato nell'outbox,
dimensione, SHA-256 e struttura EPUB della richiesta `pending` vengono tutti
riverificati. Una richiesta `sent` mantiene gli stessi campi strutturali e la
stessa ricevuta idempotente; il suo allegato può essere rimosso dopo il
completamento. La ricevuta non prova la ricezione, la consegna o la conversione
finale sul dispositivo Kindle.

### Ingresso article

Gli URL HTTP non riconosciuti come YouTube seguono una pipeline distinta:

1. download HTML con user agent dichiarato;
2. lettura dei metadati Open Graph e JSON-LD;
3. estrazione del contenitore `post-body` o `entry-content`;
4. esclusione del boilerplate della pagina;
5. registrazione separata dei riferimenti scientifici;
6. produzione di `article.analysis.md`;
7. successiva revisione editoriale e pubblicazione condivisa.
