# Policy sulla lingua della documentazione

[English](../documentation-policy.md) | [Italiano](documentation-policy.md)

## Lingua canonica

L'inglese è la lingua canonica e predefinita della documentazione pubblica
mantenuta. L'italiano è una traduzione ufficialmente mantenuta per le famiglie
di documenti indicate come bilingui di seguito.

Quando il testo inglese e quello italiano divergono, il documento inglese è la
fonte autorevole. Una traduzione deve preservare requisiti, esempi, avvisi,
limitazioni e significato tecnico; non deve essere un riassunto abbreviato.

Comandi, opzioni CLI, variabili d'ambiente, percorsi, nomi di file e snippet di
codice non vengono tradotti.

## Nomi e navigazione

- I documenti alla root usano `.it.md` per il mirror italiano.
- I documenti canonici sotto `docs/` sono in inglese.
- Le traduzioni italiane mantenute sotto `docs/it/` preservano lo stesso nome
  file e la stessa struttura relativa delle directory.
- Ogni coppia mantenuta inizia con link reciproci visibili `English` e
  `Italiano`.
- I link interni dovrebbero restare nella lingua del lettore quando esiste un
  mirror mantenuto. Altrimenti possono puntare alla sorgente canonica inglese.

## Insieme bilingue mantenuto

L'insieme bilingue iniziale mantenuto è:

- `README.md` / `README.it.md`;
- `docs/documentation-policy.md` / `docs/it/documentation-policy.md`;
- `docs/architecture.md` / `docs/it/architecture.md`.

Gli altri documenti non acquisiscono automaticamente un obbligo di traduzione.

## Documentazione storica e di release

`CHANGELOG.md` resta un unico file di cronologia delle release. Tutto il
contenuto già esistente quando è stata introdotta questa policy bilingue,
compresa la sezione `[Unreleased]` allora corrente, è grandfathered e rimane
invariato nella lingua originale. La prima voce di changelog aggiunta dopo la
migrazione bilingue e tutte le nuove voci successive devono usare l'inglese.

Le note di release storiche, incluso `docs/release-notes-v0.4.0.md`, restano
nella lingua originale e non richiedono mirror mantenuti.

Anche i documenti storici o completati di design e tracking non richiedono
automaticamente una traduzione.

Gli Architecture Decision Record sono record tecnici canonici in inglese e non
richiedono mirror italiani salvo modifica esplicita di questa policy.

## Flusso di sincronizzazione

Una modifica a un documento bilingue mantenuto deve:

1. valutare se il mirror italiano richiede la stessa modifica;
2. aggiornare entrambi i file nella stessa modifica quando cambia il significato
   tecnico;
3. preservare i selettori di lingua reciproci;
4. mantenere invariati comandi, opzioni, variabili d'ambiente, percorsi, nomi
   di file e snippet di codice;
5. eseguire i test della documentazione.

Eseguire i controlli mirati con:

```bash
python -m unittest tests.test_documentation
```

I controlli verificano le coppie richieste, i selettori di lingua reciproci e
la validità dei link Markdown relativi. Non effettuano traduzione automatica o
confronto semantico; la parità semantica resta responsabilità della review.

## Non-obiettivi

Questa policy non introduce localizzazione runtime o CLI, traduzione di prompt
o template, traduzione automatica, strumenti di confronto semantico, un
generatore di siti documentali o una piattaforma di gestione delle traduzioni.
Il materiale di studio privato resta fuori dal repository e fuori dal
contratto di documentazione bilingue.
