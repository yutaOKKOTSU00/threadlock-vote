<div align="center">

# 🗳️ threadlock-vote

**Simulation d'un système de vote électronique sécurisé**
_Étude de cas en programmation concurrente — Python Threading_

![Python](https://img.shields.io/badge/Python-3.11+-4f8ef7?style=flat-square&logo=python&logoColor=white)
![Threading](https://img.shields.io/badge/Threading-Lock%20%7C%20Event%20%7C%20Queue-22c55e?style=flat-square)
![Tkinter](https://img.shields.io/badge/Interface-Tkinter-a855f7?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-f59e0b?style=flat-square)

</div>

---

## ✨ Aperçu

**threadlock-vote** simule un scrutin électronique où plusieurs électeurs votent **en parallèle** (chacun dans son propre thread). Le projet démontre comment garantir l'intégrité d'un vote dans un environnement concurrent grâce aux mécanismes de synchronisation Python.

L'interface graphique visualise **en temps réel** l'état de chaque thread — tu vois littéralement les threads se bousculer pour accéder au verrou.

---

## 🖥️ Interface

```
┌──────────────────────────────────────────────────────────────────┐
│  THREADS EN COURS D'EXECUTION                   15 threads actifs│
├────────────┬─────────────┬──────────────────┬────────────┬───────┤
│ THREAD ID  │ TYPE        │ ETAT ACTUEL      │ PROGRESS   │ VOTE  │
├────────────┼─────────────┼──────────────────┼────────────┼───────┤
│ E001       │ Electeur    │ ✅ VOTE ACCEPTE  │ ██████████ │ Alice │
│ E002       │ Electeur    │ 🔒 ATTEND VERROU │ █████░░░░░ │  —    │
│ E003       │ Electeur    │ 🌐 RESEAU...     │ ██░░░░░░░░ │  —    │
│ E004       │ Electeur    │ 🚫 DOUBLE BLOQUE │ ██████████ │  —    │
│ D1         │ Depouilleur │ 🔍 DEPOUILLEMENT │ ████░░░░░░ │  —    │
└────────────┴─────────────┴──────────────────┴────────────┴───────┘
```

---

## ⚙️ Mécanismes implémentés

| Mécanisme | Rôle dans le projet |
|---|---|
| `threading.Lock()` | Protège la section critique du bureau de vote — un seul thread à la fois |
| `threading.Event()` | Coup d'envoi simultané pour tous les électeurs |
| `Queue` | Urne numérique thread-safe + communication GUI ↔ backend |
| **Opération atomique** | Vérification ET enregistrement du vote dans le même bloc verrouillé |
| **Sentinelle `None`** | Signal d'arrêt propre pour chaque thread dépouilleur (anti-deadlock) |

---

## 🚀 Lancement

```bash
# Cloner le repo
git clone https://github.com/<ton-pseudo>/threadlock-vote.git
cd threadlock-vote

# Aucune dépendance externe — uniquement la stdlib Python
python vote_gui.py
```

> Nécessite **Python 3.11+** et **Tkinter** (inclus par défaut avec Python sur Windows et macOS).
> Sur Linux : `sudo apt install python3-tk`

---

## 📁 Structure

```
threadlock-vote/
│
├── vote_gui.py          # Application principale (interface + backend)
├── rapport_TP.pdf       # Rapport de TP complet
└── README.md
```

---

## 🔍 Ce que le projet démontre

### Le problème sans protection

```
E005     vérifie → "déjà voté ?" → NON ✓
                                         ← (E005 interrompu par E005-bis)
E005-bis vérifie → "déjà voté ?" → NON ✓   (bug ! E005 n'est pas encore enregistré)
E005     vote   → ACCEPTÉ ✓
E005-bis vote   → ACCEPTÉ ✓   ← DOUBLE VOTE
```

### La solution avec `Lock`

```python
with self._verrou:              # ← tourniquet : un seul thread entre
    if eid in self._ayant_vote:
        return False            # double vote → refusé
    self._ayant_vote.add(eid)   # vérification + enregistrement = atomique
    self._urne.put(choix)
                                # ← verrou libéré automatiquement
```

---

## 🎛️ Paramètres configurables

Depuis l'interface graphique, avant de lancer un scrutin :

| Paramètre | Description | Défaut |
|---|---|---|
| **Électeurs** | Nombre de threads électeurs créés | 12 |
| **% double vote** | Proportion d'électeurs qui tentent de voter deux fois | 25 % |
| **Délai réseau (ms)** | Latence simulée — plus il est élevé, plus la contention est visible | 800 ms |

> 💡 **Astuce** : mets le délai réseau à 2000 ms et le % double vote à 50 % pour voir le maximum de threads en état `ATTEND VERROU` simultanément.

---

## 📄 Licence

Distribué sous licence MIT. Voir `LICENSE` pour plus d'informations.

---

<div align="center">
  <sub>Réalisé dans le cadre du cours de <b>Programmation Concurrente</b> — 2024/2025</sub>
</div>
