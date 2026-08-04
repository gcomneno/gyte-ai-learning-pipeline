# Changelog

Tutte le modifiche rilevanti di GYTE Study Tools sono documentate
in questo file.

Il progetto segue il versionamento semantico.

## [Unreleased]

### Aggiunto

- rilevamento automatico tra sorgenti YouTube e articoli;
- ingestione di articoli HTML;
- estrazione dei contenitori Blogger `post-body` ed `entry-content`;
- lettura di metadati Open Graph e JSON-LD;
- dossier `article.analysis.md`;
- registrazione separata dei riferimenti scientifici;
- protocollo esplicito per distinguere fonte, evidenza e inferenza.

## [0.4.0] - 2026-08-03

Prima release assistita completa.

### Aggiunto

- comando locale `gyte-lesson-kindle`;
- controllo dei prerequisiti dell'ambiente;
- ispezione dei video YouTube tramite `yt-dlp`;
- recupero di titolo, canale, durata, lingua, data e ID;
- selezione preferenziale delle caption `it-orig`, poi `it`;
- creazione di workspace privati stabili e riavviabili;
- persistenza di `metadata.json` e `pipeline-state.json`;
- acquisizione dei transcript tramite GYTE;
- adozione sicura di transcript e output già esistenti;
- normalizzazione delle entità HTML;
- reflow AI-friendly;
- controllo del conteggio delle parole;
- generazione di `transcript.analysis.md`;
- pubblicazione da Markdown revisionato;
- generazione indipendente di HTML, PDF ed EPUB;
- validazione strutturale dell'EPUB;
- controllo del testo recuperabile da PDF ed EPUB;
- backup timestampati degli output precedenti;
- manifest di pubblicazione con hash SHA-256;
- test unitari e collaudo end-to-end reale.

### Limitazioni note

- la composizione della Lesson Learned richiede ancora un passaggio
  editoriale assistito;
- il fallback audio con Whisper non è ancora implementato;
- la generazione automatica tramite provider LLM non è ancora disponibile.
