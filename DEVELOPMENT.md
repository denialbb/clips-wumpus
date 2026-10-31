# Linee Guida di Sviluppo e Standard di Progetto

Documento interno per lo sviluppo del progetto e criteri di qualità del codice da consegnare per la valutazione d'esame.

---

## 1. Standard di Codice e Commenti

- **Stile essenziale e idiomatico**: scrivere codice chiaro, modulare e privo di ridondanze. Rispettare le convenzioni idiomatiche CLIPS e PEP 8 per Python.
- **Commenti descrittivi e non storici**:
  - Commentare *cosa* fa il blocco logico e il *perché* di scelte euristiche o di priorità (salience).
  - **Vietati commenti storici o di log delle modifiche** (es. "modificato il giorno X", "risolto bug Y", "vecchia versione commentata", "refactoring di..."). La cronologia appartiene esclusivamente ai commit Git.
  - Nessun blocco di codice obsoleto lasciato commentato nel sorgente.

---

## 2. Test-Driven Development (TDD) e Complessità Ciclomatica

- **Flusso Red-Green**:
  - Ogni nuova funzionalità (modulo di percezione, inferenza pozzi, pianificazione rientro) deve essere preceduta o accompagnata da test specifici in `tests/`.
  - I test partono in stato *failing* (Red) ed evolvono a *passing* (Green) con l'implementazione della logica.
- **Controllo Complessità Ciclomatica**:
  - Mantenere le funzioni corte e con percorsi decisionali chiari.
  - Soglia massima di complessità ciclomatica per funzione: $B$ (complessità $\le 10$).
  - I test di complessità vengono eseguiti automaticamente tramite `radon` e `flake8` ad ogni esecuzione di `pytest`.

---

## 3. Automazione CI (GitHub Actions)

La pipeline CI (`.github/workflows/ci.yml`) viene attivata ad ogni push o pull request su `main`:
1. Verifica sintattica e assenza di errori di runtime su Python e CLIPS.
2. Calcolo e validazione della complessità ciclomatica su tutti gli script.
3. Esecuzione suite `pytest` (inclusi contratti dei moduli e scenari di simulazione).

Per eseguire i controlli localmente prima del commit:
```bash
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
radon cc -s -a -nb tests/
pytest -v tests/
```

---

## 4. Integrità della Consegna Accademica

Il repository e i relativi documenti saranno sottoposti a revisione e valutazione da parte dei docenti:
- Nessun marcatore, template generato o commento riconducibile a strumenti di intelligenza artificiale deve essere presente nel codice, nei commit o nella documentazione.
- Mantenere commit atomici con messaggi convenzionali chiari (`feat:`, `fix:`, `test:`, `docs:`), scritti in prima persona plurale o stile imperativo standard.
- Tutta la documentazione di supporto (`README.md`, slide di presentazione) deve riflettere la terminologia del corso e l'esperienza progettuale diretta.
