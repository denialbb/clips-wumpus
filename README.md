# clips-wumpus — L'oro del Wumpus

Progetto di **Intelligenza Artificiale e Laboratorio** (a.a. 2025–2026), modulo *Planning e Sistemi a Regole* (Prof. Micalizio).

Agente a regole implementato in CLIPS per l'esplorazione autonoma della tana del Wumpus, integrato tramite `clipspy` con simulatore Python ad eventi discreti.

---

## 1. Regole del Dominio & Meccaniche

- **Mondo**: Griglia sconosciuta, completamente buia. Posizione di partenza ed uscita in `(0, 0)`.
- **Percezioni**:
  - `(percept (x ?x) (y ?y) (steps ?s) (breeze ?b) (stench ?st) (glitter ?g) (energy ?e))`
  - `(counter (step ?s))`
  - Segnali locali (vicini ortogonali): `stench` (Wumpus adiacente), `breeze` (pozzo adiacente), `glitter` (oro nella cella corrente).
- **Azioni**:
  - Movimento: `up`, `down`, `left`, `right`
  - Raccolta oro: `grab` (+100 oro)
  - Conclusione: `quit` (valida solo in `(0, 0)`)
  - Ipotesi pozzi: `pit-north`, `pit-south`, `pit-west`, `pit-east` (+25 oro se corretto, -25 se errato)
- **Energia**: Limitata; ogni azione consuma energia. Urtare i muri (appresi sbattendoci contro) comporta consumo addizionale.
- **Protocollo**: Asserire esattamente **UN** solo fatto `(action (move ?act))` per ogni ciclo/step temporale. Vecchi fatti `percept` vanno rimossi dalla working memory.

---

## 2. Architettura degli Agenti

Obbligatorio l'uso dei **moduli CLIPS** per scandire il ciclo percettivo-decisionale:

```mermaid
flowchart LR
    MAIN[MAIN] --> PERCEPT[PERCEZIONE]
    PERCEPT --> MAP[MAPPA / INFERENZA]
    MAP --> HYPO[IPOTESI PIT]
    HYPO --> DECIDE[DECISIONE / GOAL]
    DECIDE --> ACT[AZIONE]
```

1. **`agent_random.clp`**: Baseline stupida fornita con il simulatore (movimenti casuali).
2. **`agent.clp` / `agent_expert.clp`**: Agente intelligente a regole:
   - Rappresentazione esplicita della mappa esplorata, caselle sicure, muri e celle sospette.
   - Inferenza logica / Certainty Factors per la stima della presenza di pozzi prima di rischiare o formulare ipotesi `pit-*`.
   - Pianificazione del percorso di rientro a `(0, 0)` calibrata sull'energia residua.

*Riferimento stile e moduli*: [`denialbb/mastermind`](https://github.com/denialbb/mastermind).

---

## 3. Setup & Esecuzione

```bash
# Setup ambiente
python3 -m venv .venv
source .venv/bin/activate
pip install clipspy

# Su sistemi Debian/Ubuntu, se manca Tk:
# sudo apt install python3-tk

# Esecuzione agente base / casuale
python3 wumpus.py -m map1.json -a agent_random.clp

# Esecuzione agente intelligente
python3 wumpus.py -m map1.json -a agent.clp
```

---

## 4. Deliverable d'Esame

- Agente intelligente (`agent.clp`) + baseline (`agent_random.clp`) con confronto quantitativo (oro raccolto, sopravvivenza, energia residua, accuratezza ipotesi pozzi).
- Presentazione (~10 min) con architettura delle regole e strategie.
- Demo live (anche su mappe ignote) e domande orali su concetti teorici CLIPS (working memory, pattern matching RETE, agenda, cicli di esecuzione, rifrazione).
