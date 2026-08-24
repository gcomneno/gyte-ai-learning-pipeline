# GYTE AI Learning Pipeline

[English](README.md) | [Italiano](README.it.md)

Companion project di [GYTE](https://github.com/gcomneno/gyte) per trasformare
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
  → lezione sorgente revisionata
  → checkpoint di review esplicito
  → PDF ed EPUB
  → validazione
  → richiesta Kindle locale
```

## Stato

La pipeline assistita è disponibile per:

1. ispezione di video YouTube;
2. acquisizione e normalizzazione dei transcript;
3. preparazione del materiale di analisi;
4. registrazione di un checkpoint di review esplicito per un workspace privato esistente;
5. pubblicazione della lezione sorgente con checkpoint in Markdown, HTML, PDF ed EPUB;
6. preparazione riavviabile della consegna Kindle;
7. ingestione di articoli.

La redazione della lezione sorgente resta un passaggio editoriale controllato.
Il checkpoint di review registra l'accettazione locale esplicita di byte esatti,
ma non prova comprensione umana, correttezza fattuale, verità della fonte,
completamento del fact-checking, approvazione AI o qualità della lezione. Il
fallback audio con Whisper non è ancora implementato.

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
~/.local/share/gyte-study-private-material
```

Può essere sostituita con `--work-root` oppure impostando
`GYTE_STUDY_WORK_ROOT`.

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

La pipeline deterministica di base non richiede `giadaware-ai`.

L'operazione opzionale `--ai-advisory` richiede che il package `giadaware-ai`
sia importabile dallo stesso interprete Python usato da
`gyte-lesson-kindle`. GiadaWare AI è attualmente distribuito separatamente e
non è pubblicato su PyPI; il relativo wheel deve essere installato seguendo le
istruzioni di installazione del repository `giadaware-ai`. L'installer GYTE
intenzionalmente non cerca checkout sibling, non modifica `PYTHONPATH` per
package esterni e non installa automaticamente questa dipendenza opzionale.

Se `giadaware-ai` o la sua composizione Ollama non sono importabili,
`--ai-advisory` registra un fallimento opzionale `configuration` preservando
la preparation deterministica già riuscita.

## Principi

Le capability AI sono opzionali e advisory. L'output AI non costituisce mai
autorità editoriale e l'assenza o il fallimento dell'AI non deve impedire alla
pipeline deterministica di base di continuare. Gli advisory AI sono operazioni
esplicite e non sono fasi numerate né autorità di stato della pipeline.

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

## Advisory AI opzionale

L'advisory AI è richiesto solo esplicitamente:

```bash
GYTE_AI_MODEL="qwen2.5:1.5b-instruct" \
gyte-lesson-kindle --ai-advisory URL
```

Per articoli e video usa solo il materiale di analisi preparato corrente:

- `transcript.analysis.md` per YouTube;
- `article.analysis.md` per articoli.

L'input canonico deve essere un figlio diretto del workspace, un file regolare,
non un symlink, non vuoto e UTF-8 valido. I byte esatti dell'input producono
SHA-256 e byte count prima della decodifica e dell'invio alla capability
semantica `analyze_learning_source(text)`.

L'operazione scrive atomically:

```text
WORKSPACE/learning-source.analysis.ai.json
```

Il nome file e l'identità semantica dell'artefatto sono distinti. L'envelope
contiene:

```json
{
  "schema_version": 1,
  "artifact": "learning-source.analysis.ai",
  "authority": "ai-advisory",
  "status": "complete",
  "provenance": {
    "source_type": "youtube|article",
    "canonical_input": "transcript.analysis.md|article.analysis.md",
    "canonical_input_sha256": "...",
    "canonical_input_byte_count": 123
  },
  "payload": {
    "central_thesis": "...",
    "key_concepts": [],
    "source_claims": [],
    "practical_applications": [],
    "limitations": [],
    "review_questions": []
  },
  "failure": null
}
```

Un fallimento AI opzionale usa `status: "failed"`, `payload: null` e
`failure.kind` tra `configuration`, `unavailable`, `timeout`,
`invalid-response` e `unsupported`. Un artefatto fallito non è riusabile come
successo; un successo riusabile richiede `status == "complete"` e gli stessi
byte canonici. `--force` rigenera anche l'advisory. L'advisory non scrive
`stages.ai-advisory`, non muta `pipeline-state.json`, non crea lezioni,
pubblicazioni o consegne.

Per limitarsi ai metadati:

```bash
gyte-lesson-kindle --inspect-only URL_YOUTUBE
```

Per rigenerare gli output della preparazione:

```bash
gyte-lesson-kindle --force URL_YOUTUBE
```

Il fallback audio con Whisper non è ancora implementato.

## Terza fase disponibile: review

L'invocazione normale con il solo URL è acquisizione e preparazione: risolve o
crea il workspace privato, ispeziona la fonte quando necessario e prepara il
materiale di analisi video o articolo. Review e pubblicazione downstream sono
operazioni locali su un workspace privato esistente risolto dallo stesso URL
sorgente; non riacquisiscono la fonte e non rieseguono la preparazione.

Dopo la revisione editoriale, `lesson.md` è la lezione sorgente stabile: un
handoff editoriale autosufficiente destinato a TritaLeLe. GYTE AI Learning Pipeline non
invoca TritaLeLe e non dipende da dettagli interni di LeLe Manager.

La lezione sorgente deve rispettare questo contratto editoriale minimo:

- esattamente un titolo Markdown H1;
- uno scopo breve o una tesi centrale;
- sezioni H2 tematiche e ragionevolmente autosufficienti;
- separazione esplicita tra fatti, interpretazioni della fonte e valutazione critica;
- concetti ed esempi rielaborati, senza riprodurre l'intero transcript;
- applicazioni pratiche;
- limiti o affermazioni non supportate;
- domande di revisione o riflessione.

`transcript.analysis.md` e `article.analysis.md` restano materiali assistiti
per la revisione; la lezione sorgente viene redatta e controllata dall'editor,
senza generazione automatica. Registra il checkpoint esplicito con:

```bash
gyte-lesson-kindle \
  --review-from "/percorso/lesson.md" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

`--review-from` risolve localmente un workspace privato esistente, richiede
`prepare` completo, valida il Markdown revisionato incluso esattamente un H1,
scrive `reviewed-source-checkpoint.json` e registra `stages.review` in
`pipeline-state.json`. Non riacquisisce la fonte, non riesegue inspect, non
riesegue prepare, non reingerisce un articolo, non esegue AI, non pubblica e
non muta artefatti di evidenza o preparazione.

Il checkpoint vincola i byte esatti della sorgente revisionata, l'identità
sorgente e i byte degli artefatti di evidenza/preparazione richiesti: per i
video, `metadata.json`, `source-url.txt`, `transcript.raw.txt`,
`transcript.normalized.txt`, `transcript.analysis.txt` e
`transcript.analysis.md`; per gli articoli, `metadata.json`, `source-url.txt`,
`article.raw.html`, `article.extracted.md` e `article.analysis.md`.

La scala di autorità resta esplicita:

```text
evidenza sorgente
!= evidenza normalizzata
!= analisi preparata
!= candidato editoriale
!= sorgente revisionata
!= derivato pubblicato
```

Materiale preparato o generato non diventa mai implicitamente autorità di
pubblicazione. Il checkpoint prova solo che un'operazione di checkpoint
esplicita è avvenuta su byte esatti della sorgente revisionata e degli
artefatti di evidenza/preparazione. Non prova lineage editoriale causale
dall'analisi preparata. Se dopo la review cambiano lezione revisionata,
identità sorgente, metadati, URL sorgente, evidenza raw o normalizzata, oppure
analisi preparata, l'idoneità alla pubblicazione diventa stale; rieseguire
`--review-from` esplicitamente quando il nuovo materiale corrente è accettabile.

## Quarta fase disponibile: publish

Anche `--publish-from` è un'operazione downstream locale su un workspace
esistente. Non riacquisisce la fonte, non riesegue inspect, non riesegue
prepare e non reingerisce un articolo. Pubblica con:

```bash
gyte-lesson-kindle \
  --publish-from "/percorso/lesson.md" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

La pubblicazione richiede un checkpoint di review esplicito corrente e valido e
lo valida prima di mutare gli output di pubblicazione. Fallisce se la lezione,
l'identità sorgente o gli artefatti di evidenza/preparazione richiesti sono
cambiati dopo la review. Genera, dalla stessa sorgente semantica:

- Markdown pubblicato;
- HTML;
- PDF;
- EPUB;
- `publication-manifest.json` con hash SHA-256.

Lo schema del manifest di pubblicazione resta v2. I nuovi manifest possono
includere `review_checkpoint` con `relationship`, `checkpoint_id`,
`checkpoint_sha256` e `created_at`; lo SHA è l'identità esatta del checkpoint
validata prima del lavoro di pubblicazione. Manifest v2 validi già prodotti
senza `review_checkpoint` restano validi per la consegna Kindle. Un vecchio
workspace privato senza checkpoint esplicito deve eseguire `--review-from` una
volta prima della successiva pubblicazione, ma questo non invalida una
pubblicazione manifest-v2 valida già prodotta per la consegna. Delivery accetta
entrambe le forme v2 valide e non riapre `reviewed-source-checkpoint.json` né
acquisisce autorità su transcript privati, evidenza o artefatti di preparazione.

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
  --publish-from "/percorso/lesson.md" \
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
  → checkpoint di review
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
