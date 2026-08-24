# Architettura iniziale

[English](../architecture.md) | [Italiano](architecture.md)

## Confini

### GYTE

Fornisce i mattoni generali per ottenere e preparare il testo:

- `gyte-transcript`
- `gyte-reflow-text`

### GYTE AI Learning Pipeline

Le capability AI opzionali possono assistere l'analisi, ma non possiedono lo
stato della pipeline né l'autorità editoriale. La loro assenza o il loro
fallimento non deve invalidare fasi deterministiche già valide.

Orchestra il workflow didattico ed editoriale:

- identificazione del video;
- creazione della directory di lavoro;
- selezione delle caption;
- fallback di trascrizione;
- normalizzazione;
- validazione;
- creazione del pacchetto di analisi;
- checkpoint esplicito della sorgente revisionata;
- pubblicazione della lezione sorgente revisionata con checkpoint;
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

4. `review`
   - operazione downstream locale per un workspace privato esistente;
   - valida la lezione sorgente revisionata in Markdown;
   - richiede esattamente un H1 e preparazione completa;
   - scrive `reviewed-source-checkpoint.json` schema v1;
   - registra `stages.review` come stato di restart/controllo.

5. `compose`
   - versione assistita: attende la lezione sorgente revisionata;
   - versione completa futura: usa un provider LLM configurabile.

6. `publish`
   - operazione downstream locale per un workspace privato esistente;
   - richiede un checkpoint di review esplicito corrente e valido;
   - valida il checkpoint prima di mutare gli output di pubblicazione;
   - sorgente unica Markdown;
   - generazione indipendente di PDF ed EPUB;
   - metadati coerenti;
   - backup degli output precedenti.

7. `validate`
   - integrità ZIP dell'EPUB;
   - verifica del mimetype;
   - controllo del testo recuperabile;
   - riepilogo finale.

8. `delivery`
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

L'operazione opzionale `--ai-advisory` resta intenzionalmente fuori dall'elenco
numerato delle fasi. Produce un artefatto advisory privato senza autorità sullo
stato della pipeline.

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

### Advisory AI opzionale

`--ai-advisory SOURCE_URL` è un'operazione esplicita e non stateful dopo la
preparazione deterministica. Non viene eseguita durante review, pubblicazione
o delivery e non crea lezione sorgente, artefatto di pubblicazione, richiesta
Kindle o voce di stato `stages.ai-advisory`.

L'input canonico è fisso per tipo sorgente:

- YouTube: `transcript.analysis.md`;
- articolo: `article.analysis.md`.

L'input deve essere un figlio diretto del workspace privato. Traversal, path
esterni, symlink, file non regolari, file mancanti, file vuoti e UTF-8 non
valido falliscono in modo chiuso come `AIAdvisoryError` deterministico.

Per generare un advisory fresco, i byte esatti dell'input vengono sottoposti a
hash e conteggio prima della decodifica UTF-8 stretta. Il testo viene passato
alla capability semantica GiadaWare AI tramite la chiamata pubblica:

```python
ai.analyze_learning_source(text)
```

La composizione di produzione è lazy e richiede `GYTE_AI_MODEL`.
`GYTE_AI_BASE_URL` e `GYTE_AI_TIMEOUT` configurano opzionalmente il backend
Ollama. Se `giadaware_ai` o la composizione Ollama non possono essere importati,
l'artefatto advisory registra un fallimento opzionale atteso con
`kind: "configuration"`. Un `AIUnavailableError` reale mappa a
`kind: "unavailable"`.

Solo cinque fallimenti GiadaWare AI attesi vengono convertiti in fallimenti
advisory:

- `AIConfigurationError` -> `configuration`;
- `AIUnavailableError` -> `unavailable`;
- `AITimeoutError` -> `timeout`;
- `AIInvalidResponseError` -> `invalid-response`;
- `AIUnsupportedCapabilityError` -> `unsupported`.

Le eccezioni inattese non vengono convertite in fallimenti di disponibilità. I
risultati locali/integration malformati falliscono in modo chiuso come
`AIAdvisoryError`, tranne il percorso reale GiadaWare AI
`AIInvalidResponseError`, che resta un fallimento advisory atteso
`invalid-response`.

L'output sul filesystem è:

```text
WORKSPACE/learning-source.analysis.ai.json
```

L'identità semantica dell'artefatto nell'envelope è:

```json
"artifact": "learning-source.analysis.ai"
```

Il riuso di un successo richiede `status == "complete"` e corrispondenza esatta
di provenienza: tipo sorgente, nome dell'input canonico, SHA-256 e byte count.
Gli artefatti falliti non sono mai riusabili come successo. Cambiamenti dei
byte anche a parità di lunghezza invalidano il riuso perché viene controllato
lo SHA-256.

### Fase review

La fase `review` è il checkpoint esplicito di autorità tra evidenza e sorgente
revisionata. La scala di autorità non deve collassare:

```text
evidenza sorgente
!= evidenza normalizzata
!= analisi preparata
!= candidato editoriale
!= sorgente revisionata
!= derivato pubblicato
```

`--review-from LEZIONE SOURCE_URL` risolve localmente da `SOURCE_URL` un
workspace privato esistente. Non riacquisisce la fonte, non riesegue inspect,
non riesegue prepare, non reingerisce un articolo, non pubblica, non esegue AI
e non muta artefatti di evidenza o preparazione. Richiede `prepare` completo,
valida il Markdown revisionato incluso esattamente un H1, scrive
`reviewed-source-checkpoint.json` schema v1 e registra `stages.review` in
`pipeline-state.json`.

`reviewed-source-checkpoint.json` è evidenza privata autorevole della review.
Vincola i byte esatti della sorgente revisionata, l'identità sorgente osservata
e i byte esatti degli artefatti di evidenza/preparazione richiesti. Per i video
sono `metadata.json`, `source-url.txt`, `transcript.raw.txt`,
`transcript.normalized.txt`, `transcript.analysis.txt` e
`transcript.analysis.md`. Per gli articoli sono `metadata.json`,
`source-url.txt`, `article.raw.html`, `article.extracted.md` e
`article.analysis.md`.

`stages.review` è metadato di restart e controllo: un puntatore/riassunto hash
del checkpoint, non autorità editoriale in sé. Sostituzione del checkpoint e
aggiornamento dello stato sono fail-safe; un aggiornamento stato fallito non
deve lasciare lo stato puntato silenziosamente a un checkpoint diverso.

Il checkpoint prova solo che è avvenuta un'operazione esplicita di checkpoint,
i byte esatti della sorgente revisionata, l'identità sorgente osservata per
quel checkpoint e i byte esatti degli artefatti di evidenza/preparazione
richiesti. Non prova comprensione umana, correttezza fattuale, verità della
fonte, completamento del fact-checking, approvazione AI, qualità della lezione
o derivazione causale/lineage editoriale dall'analisi preparata.

Modificare lezione revisionata, identità sorgente, metadati, URL sorgente,
evidenza raw o normalizzata, oppure analisi preparata rende il checkpoint stale
per la pubblicazione. Rieseguire `--review-from` ripristina esplicitamente
l'idoneità alla pubblicazione solo se il nuovo materiale corrente è accettabile.

### Fase publish

La fase `publish`:

- accetta una lezione sorgente revisionata in Markdown da un workspace locale esistente;
- non riacquisisce la fonte, non riesegue inspect, non riesegue prepare e non reingerisce un articolo;
- richiede un checkpoint di review esplicito corrente e valido prima di mutare output;
- ricava il titolo dall'H1;
- conserva il titolo H1 senza aggiungere etichette;
- renderizza HTML semantico senza dipendenze Python esterne;
- genera PDF ed EPUB separatamente tramite Calibre;
- valida struttura EPUB e testo recuperabile;
- valida il testo recuperabile dal PDF;
- conserva gli output precedenti con backup timestampati;
- genera `publication-manifest.json` schema v2 con hash SHA-256;
- registra la pubblicazione nello stato della pipeline.

Un `--output-dir` esplicito può collocare gli output di pubblicazione fuori dal
workspace. Quella directory ha autorità di pubblicazione solo perché
`publish_lesson` registra nello stato pipeline i percorsi concreti del manifest
e dell'EPUB.

Il manifest di pubblicazione v2 registra solo provenienza di pubblicazione a
livello di byte e contesto sorgente/preparazione osservato:

- `reviewed_source.sha256` è l'hash dei byte esatti della sorgente Markdown
  letta da `publish_lesson`;
- `files.markdown.sha256` è l'hash dei byte esatti della copia Markdown
  installata nella pubblicazione e deve coincidere con
  `reviewed_source.sha256`;
- `files.html`, `files.pdf` e `files.epub` sono artefatti di pubblicazione
  derivati con `role` e relazioni `derived_from` esplicite;
- `source_context.metadata_sha256`, quando presente, è solo l'hash dei byte
  esatti di `metadata.json` osservato al momento della pubblicazione;
- `source_context.prepared_artifacts[]` registra solo artefatti di analisi
  preparata osservati al momento della pubblicazione e i loro hash esatti.

La issue #17 ha stabilito provenienza di pubblicazione a livello di byte e
contesto sorgente/preparazione osservato. Non ha provato lineage editoriale. La
issue #18 aggiunge il checkpoint di review esplicito che la pubblicazione deve
validare prima di mutare output.

Lo schema del manifest di pubblicazione resta v2. I nuovi manifest possono
contenere `review_checkpoint` con `relationship`, `checkpoint_id`,
`checkpoint_sha256` e `created_at`. Lo SHA è l'identità esatta del checkpoint
validata prima del lavoro di pubblicazione. Manifest schema-v2 validi senza
`review_checkpoint` restano evidenza di pubblicazione legacy valida per la
consegna Kindle.

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

Delivery accetta solo una pubblicazione completa il cui manifest sia validato
come schema v2, includendo sia manifest legacy validi senza `review_checkpoint`
sia manifest nuovi con `review_checkpoint`. Il percorso EPUB del manifest deve
concordare con lo stato publish, restare relativo dentro la directory di
pubblicazione, identificare un EPUB regolare non vuoto, avere struttura EPUB
valida e corrispondere allo SHA-256 registrato. Delivery non riapre
`reviewed-source-checkpoint.json`, non attraversa metadati, transcript, analisi
preparata o percorsi arbitrari menzionati dal manifest, e non acquisisce
autorità su artefatti privati di evidenza/preparazione.

Quando la pubblicazione ha usato un `--output-dir` esterno, delivery può
preparare l'handoff Kindle da quella directory di pubblicazione registrata
nello stato. I valori `files.*.path` del manifest restano relativi a
`publication-manifest.json` e non possono autorizzare accessi a percorsi non
correlati.

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
