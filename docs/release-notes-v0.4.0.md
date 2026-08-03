# GYTE Study Tools v0.4.0

## Prima release assistita completa

GYTE Study Tools trasforma un URL YouTube in materiale didattico
revisionabile e successivamente in PDF ed EPUB validati.

## Flusso operativo

Prima fase:

```bash
gyte-lesson-kindle "URL_YOUTUBE"
```

Il comando:

1. ispeziona il video;
2. seleziona le caption preferibili;
3. prepara il workspace privato;
4. acquisisce o adotta il transcript;
5. normalizza e riorganizza il testo;
6. produce `transcript.analysis.md`.

Dopo la revisione editoriale:

```bash
gyte-lesson-kindle \
  --publish-from "/percorso/Lesson Learned.md" \
  "URL_YOUTUBE"
```

La pubblicazione genera dalla stessa sorgente Markdown:

- Markdown canonico;
- HTML semantico;
- PDF;
- EPUB;
- manifest con hash SHA-256.

## Garanzie della pipeline

- nessuna sovrascrittura silenziosa;
- backup timestampati;
- workspace riavviabili;
- conteggio delle parole prima e dopo il reflow;
- validazione ZIP e mimetype dell'EPUB;
- controllo del testo recuperabile;
- separazione tra codice pubblico e materiali privati;
- stato persistente delle fasi.

## Collaudo reale

La pipeline è stata verificata da un workspace temporaneo vuoto usando
una lectio di Telmo Pievani.

Risultati:

- caption selezionata: `it-orig`, automatica;
- transcript: 5.989 parole;
- conteggio preservato dopo normalizzazione e reflow;
- PDF ed EPUB generati e validati;
- hash SHA-256 verificati;
- fasi `inspect`, `transcribe`, `prepare` e `publish` complete.

## Limitazioni

La versione 0.4.0 è assistita: la Lesson Learned viene ancora composta
e revisionata prima della pubblicazione.

Sviluppi futuri previsti:

- fallback Whisper;
- prompt editoriale definitivo e versionato;
- provider LLM configurabile;
- automazione completa opzionale;
- packaging e distribuzione semplificata.
