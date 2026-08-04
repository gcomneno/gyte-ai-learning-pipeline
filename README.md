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
  → richiesta Kindle locale
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

## Prima fase disponibile: inspect

Dato un URL YouTube, il comando recupera i metadati, individua le caption
preferibili e prepara una directory privata riavviabile:

```bash
gyte-lesson-kindle "https://www.youtube.com/watch?v=VIDEO_ID"
```

File prodotti nella directory privata:

- `source-url.txt`
- `metadata.json`
- `pipeline-state.json`

Questa fase non scarica ancora caption, audio o video.

## Seconda fase disponibile: prepare

Per impostazione predefinita, dato un URL il comando completa sia `inspect`
sia `prepare`:

```bash
gyte-lesson-kindle "https://www.youtube.com/watch?v=VIDEO_ID"
```

La fase produce o adotta in modo riavviabile:

- `transcript.raw.txt`
- `transcript.normalized.txt`
- `transcript.analysis.txt`
- `transcript.analysis.md`

Per limitarsi ai metadati:

```bash
gyte-lesson-kindle --inspect-only URL_YOUTUBE
```

Per rigenerare gli output della preparazione:

```bash
gyte-lesson-kindle --force URL_YOUTUBE
```

Il fallback audio con Whisper non è ancora implementato.

## Terza fase disponibile: publish

Dopo la revisione editoriale, la Lesson Learned deve essere salvata in
Markdown e può essere pubblicata con:

```bash
gyte-lesson-kindle \
  --publish-from "/percorso/Lesson Learned.md" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

La pubblicazione genera, dalla stessa sorgente semantica:

- Markdown canonico;
- HTML;
- PDF;
- EPUB;
- `publication-manifest.json` con hash SHA-256.

Gli output vengono salvati per impostazione predefinita in:

```text
WORKSPACE_PRIVATO/publication/
```

File precedenti con lo stesso nome vengono conservati mediante backup
timestampati. PDF ed EPUB vengono validati prima di sostituire gli output
esistenti.

## Consegna Kindle assistita

L'invio effettivo è intenzionalmente separato dal processo locale: il comando
non contiene credenziali e non accede a Gmail. Il flusso è riavviabile e ha
due transizioni esplicite:

```text
prepare locale → transfer/upload attachment → Gmail connector send → local receipt
```

1. Pubblica e prepara la richiesta pending per un indirizzo Kindle valido:

```bash
gyte-lesson-kindle \
  --publish-from "/percorso/Lesson Learned.md" \
  --kindle-email reader@kindle.com \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Il comando verifica il manifest della pubblicazione, calcola SHA-256,
crea `delivery/kindle-delivery-request.json` e mostra il percorso assoluto
dell'allegato stabile in `delivery/outbox/`. Quel percorso è locale al
workspace: non è automaticamente accessibile al Gmail connector eseguito in
un altro ambiente. Il file deve quindi essere trasferito o caricato
nell'ambiente del connector prima dell'invio. Il connector può usare
direttamente `attachment_path` soltanto se condivide lo stesso filesystem;
altrimenti il trasferimento è responsabilità dell'utente o dell'orchestratore.
SHA-256 e dimensione identificano l'artefatto esatto da trasferire. Nessuna
email viene inviata dal comando.
L'allegato è sempre una copia indipendente dell'EPUB pubblicato (mai un hard
link), installata atomicamente dopo la verifica di dimensione, SHA-256 e
struttura EPUB.

2. Dopo l'invio dal connector, registra la sua ricevuta (per esempio un ID
messaggio) senza ripubblicare né contattare la rete:

```bash
gyte-lesson-kindle \
  --record-kindle-delivery "gmail-message-id" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

La seconda transizione trova il workspace esistente dall'URL, aggiorna la
richiesta a `sent` e porta `stages.delivery` a `complete`. Ripetere la stessa
ricevuta è sicuro; una ricevuta diversa viene rifiutata. Sono accettati solo
domini esatti `kindle.com` e `free.kindle.com`. Prima della ricevuta vengono
ricontrollati il contratto JSON e l'allegato `pending`; dopo il completamento
l'allegato può essere rimosso, ma non la coerenza della richiesta `sent`.
La ricevuta attesta l'invio dal Gmail connector, non la ricezione, consegna o
conversione finale da parte del dispositivo Kindle.

## Release corrente

Versione stabile: `0.4.0`.

La pipeline assistita completa è disponibile:

```text
URL YouTube
  → inspect
  → transcript
  → prepare
  → revisione editoriale
  → publish
  → PDF + EPUB validati
```

Note complete:

- `CHANGELOG.md`
- `docs/release-notes-v0.4.0.md`

## Ingresso articoli

Il comando riconosce automaticamente gli URL non YouTube come articoli:

```bash
gyte-lesson-kindle "URL_ARTICOLO"
```

La fase genera:

- `article.raw.html`;
- `article.extracted.md`;
- `article.analysis.md`;
- `metadata.json`;
- `pipeline-state.json`.

Il dossier separa il contenuto giornalistico dai riferimenti scientifici
rilevati e include un protocollo per distinguere affermazioni della fonte,
risultati primari, inferenze e fatti ancora da verificare.
