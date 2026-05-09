"""
SYSTÈME DE VOTE SÉCURISÉ — Interface Tkinter
Visualisation des threads en temps réel
"""

import threading
import time
import random
import tkinter as tk
from tkinter import ttk
from queue import Queue, Empty
from collections import Counter

# ── Palette ──────────────────────────────────
BG     = "#0f1117"
CARD   = "#1a1d2e"
BORDER = "#2a2d3e"
ACCENT = "#4f8ef7"
GREEN  = "#22c55e"
RED    = "#ef4444"
AMBER  = "#f59e0b"
PURPLE = "#a855f7"
CYAN   = "#06b6d4"
TEXT   = "#e2e8f0"
MUTED  = "#64748b"
WHITE  = "#ffffff"

CANDIDATS       = ["Alice", "Bob", "Charlie"]
COUL_CANDS      = {"Alice": "#818cf8", "Bob": "#34d399", "Charlie": "#fb923c"}
NB_DEPOUILLEURS = 3

# Etats possibles d'un thread : (texte, couleur de fond, couleur texte)
ETATS = {
    "attente":  ("EN ATTENTE",     "#1c2230", MUTED),
    "reseau":   ("RESEAU...",       "#102040", ACCENT),
    "verrou":   ("ATTEND VERROU",   "#2d1f00", AMBER),
    "vote_ok":  ("VOTE ACCEPTE",    "#0a2e18", GREEN),
    "double":   ("DOUBLE BLOQUE",   "#2e0a0a", RED),
    "rejet":    ("REJETE",          "#2e0a0a", RED),
    "termine":  ("TERMINE",         "#111520", MUTED),
    "depoui":   ("DEPOUILLEMENT",   "#1a1040", PURPLE),
    "fusionne": ("FUSIONNE",        "#0a2e18", GREEN),
}


# ═══════════════════════════════════════
#  BACKEND
# ═══════════════════════════════════════
class BureauDeVote:
    def __init__(self, candidats, push):
        self._verrou     = threading.Lock()
        self._ayant_vote = set()
        self._urne       = Queue()
        self._candidats  = candidats
        self._push       = push   # -> GUI queue
        self._ouvert     = False

    def ouvrir(self):
        self._ouvert = True
        self._push(("LOG", "INFO", "Bureau de vote ouvert"))

    def fermer(self):
        self._ouvert = False
        self._push(("LOG", "INFO", "Bureau de vote ferme"))

    def voter(self, eid, choix):
        # signale qu'on attend le verrou
        self._push(("ETAT", eid, "verrou"))
        with self._verrou:                      # ← SECTION CRITIQUE
            if not self._ouvert:
                self._push(("ETAT", eid, "rejet"))
                self._push(("LOG", "REJET", f"{eid} : bureau ferme"))
                return False
            if eid in self._ayant_vote:
                self._push(("ETAT", eid, "double"))
                self._push(("LOG", "DOUBLE", f"{eid} : DOUBLE VOTE bloque !"))
                return False
            self._ayant_vote.add(eid)
            self._urne.put(choix)
            self._push(("ETAT",  eid, "vote_ok"))
            self._push(("LOG",  "OK", f"{eid} -> {choix}"))
            self._push(("VOTE", eid, choix))
            return True

    def cloturer_urne(self):
        for _ in range(NB_DEPOUILLEURS):
            self._urne.put(None)

    @property
    def urne(self):
        return self._urne


class Electeur(threading.Thread):
    def __init__(self, eid, bureau, signal, tentative_double, delai_max):
        super().__init__(daemon=True)
        self.eid              = eid
        self.bureau           = bureau
        self.signal           = signal
        self.tentative_double = tentative_double
        self.delai_max        = delai_max

    def run(self):
        self.signal.wait()
        self.bureau._push(("ETAT", self.eid, "reseau"))
        time.sleep(random.uniform(0.05, self.delai_max))
        self.bureau.voter(self.eid, random.choice(CANDIDATS))
        if self.tentative_double:
            time.sleep(random.uniform(0.03, 0.12))
            self.bureau.voter(self.eid, random.choice(CANDIDATS))
        self.bureau._push(("ETAT", self.eid, "termine"))


class Depouilleur(threading.Thread):
    def __init__(self, label, urne, partiaux, verrou, push):
        super().__init__(daemon=True)
        self.label    = label
        self.urne     = urne
        self.partiaux = partiaux
        self.verrou   = verrou
        self.push     = push

    def run(self):
        self.push(("ETAT", self.label, "depoui"))
        local = Counter()
        while True:
            v = self.urne.get()
            if v is None:
                break
            local[v] += 1
            self.urne.task_done()
        with self.verrou:
            self.partiaux.append(dict(local))
        self.push(("ETAT", self.label, "fusionne"))


# ═══════════════════════════════════════
#  APPLICATION
# ═══════════════════════════════════════
class VoteApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Vote Securise — Visualisation Threading")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(1050, 680)

        self._cpt      = {"OK": 0, "DOUBLE": 0, "REJET": 0}
        self._res      = Counter()
        self._actif    = False
        self._q        = Queue()
        self._rows     = {}   # eid -> (frame_etat, lbl_etat, canvas_barre, lbl_choix)

        self._build()
        self._poll()

    # ────────────────────────────────────
    #  BUILD UI
    # ────────────────────────────────────
    def _build(self):
        # En-tete
        h = tk.Frame(self, bg=BG)
        h.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(h, text="VOTE SECURISE", font=("Courier", 16, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(h, text="  —  Visualisation du multi-threading",
                 font=("Courier", 9), bg=BG, fg=MUTED).pack(side="left")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=4)

        # Controles
        c = tk.Frame(self, bg=BG)
        c.pack(fill="x", padx=20, pady=4)
        self._sp_nb    = self._spin(c, "Electeurs",       4, 100,   50)
        self._sp_pct   = self._spin(c, "% double vote",   0, 100,  50)
        self._sp_delai = self._spin(c, "Delai max (ms)", 200, 3000, 800)

        self._btn = tk.Button(c, text="  LANCER LE SCRUTIN  ",
                              font=("Courier", 10, "bold"),
                              bg=ACCENT, fg=BG, relief="flat",
                              padx=6, pady=5, cursor="hand2",
                              command=self._lancer)
        self._btn.pack(side="left", padx=(14, 6))
        tk.Button(c, text="  RESET  ", font=("Courier", 9),
                  bg=CARD, fg=MUTED, relief="flat", padx=6, pady=5,
                  cursor="hand2", command=self._reset).pack(side="left")

        # Status + barre
        sf = tk.Frame(self, bg=BG)
        sf.pack(fill="x", padx=20, pady=(3, 0))
        self._status = tk.Label(sf, text="En attente...",
                                font=("Courier", 9), bg=BG, fg=MUTED)
        self._status.pack(anchor="w")
        s = ttk.Style(self)
        s.theme_use("default")
        s.configure("v.Horizontal.TProgressbar",
                    troughcolor=CARD, background=GREEN,
                    bordercolor=BORDER, lightcolor=GREEN, darkcolor=GREEN)
        self._prog = ttk.Progressbar(sf, style="v.Horizontal.TProgressbar",
                                     length=700, mode="determinate")
        self._prog.pack(anchor="w", pady=(2, 5))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=20, pady=2)

        # Corps : panneau threads (gauche) | droite (resultats + log)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=6)
        body.columnconfigure(0, weight=6)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        self._build_thread_panel(body)
        self._build_right_panel(body)

    def _spin(self, parent, label, lo, hi, default):
        f = tk.Frame(parent, bg=BG)
        f.pack(side="left", padx=(0, 10))
        tk.Label(f, text=label, font=("Courier", 8), bg=BG, fg=MUTED).pack(anchor="w")
        v = tk.IntVar(value=default)
        tk.Spinbox(f, from_=lo, to=hi, textvariable=v, width=5,
                   font=("Courier", 10), bg=CARD, fg=TEXT,
                   buttonbackground=BORDER, relief="flat",
                   insertbackground=TEXT).pack()
        return v

    # ── Panneau de visualisation des threads ──
    def _build_thread_panel(self, parent):
        outer = tk.Frame(parent, bg=BORDER)
        outer.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        inner = tk.Frame(outer, bg=CARD, padx=10, pady=10)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # En-tete du panneau
        th = tk.Frame(inner, bg=CARD)
        th.pack(fill="x", pady=(0, 6))
        tk.Label(th, text="THREADS EN COURS D'EXECUTION",
                 font=("Courier", 10, "bold"), bg=CARD, fg=WHITE).pack(side="left")
        self._lbl_nb_threads = tk.Label(th, text="0 threads actifs",
                                         font=("Courier", 9), bg=CARD, fg=MUTED)
        self._lbl_nb_threads.pack(side="right")

        # Legende des etats
        leg = tk.Frame(inner, bg=CARD)
        leg.pack(fill="x", pady=(0, 8))
        legendes = [
            ("reseau",  "Connexion reseau"),
            ("verrou",  "Attend le verrou (Lock)"),
            ("vote_ok", "Vote accepte"),
            ("double",  "Double vote bloque"),
            ("depoui",  "Depouillement"),
            ("termine", "Termine"),
        ]
        for i, (etat, desc) in enumerate(legendes):
            _, bg_c, fg_c = ETATS[etat]
            box = tk.Frame(leg, bg=bg_c, width=12, height=12)
            box.pack(side="left", padx=(0, 3))
            tk.Label(leg, text=desc, font=("Courier", 7), bg=CARD, fg=fg_c
                     ).pack(side="left", padx=(0, 10))

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(0, 8))

        # Colonnes header
        hrow = tk.Frame(inner, bg=CARD)
        hrow.pack(fill="x", pady=(0, 3))
        tk.Label(hrow, text="THREAD ID",    font=("Courier", 8, "bold"), width=10,
                 bg=CARD, fg=MUTED, anchor="w").pack(side="left")
        tk.Label(hrow, text="TYPE",         font=("Courier", 8, "bold"), width=12,
                 bg=CARD, fg=MUTED, anchor="w").pack(side="left")
        tk.Label(hrow, text="ETAT ACTUEL",  font=("Courier", 8, "bold"), width=22,
                 bg=CARD, fg=MUTED, anchor="w").pack(side="left")
        tk.Label(hrow, text="PROGRESSION",  font=("Courier", 8, "bold"),
                 bg=CARD, fg=MUTED, anchor="w").pack(side="left", expand=True, fill="x")
        tk.Label(hrow, text="VOTE",         font=("Courier", 8, "bold"), width=10,
                 bg=CARD, fg=MUTED, anchor="w").pack(side="right")

        # Zone scrollable pour les lignes de threads
        wrap = tk.Frame(inner, bg=CARD)
        wrap.pack(fill="both", expand=True)

        canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._threads_container = tk.Frame(canvas, bg=CARD)
        self._canvas_window = canvas.create_window(
            (0, 0), window=self._threads_container, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(self._canvas_window, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        self._threads_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    def _add_thread_row(self, eid, type_label):
        """Crée une ligne visuelle pour un thread."""
        row = tk.Frame(self._threads_container, bg=CARD, pady=2)
        row.pack(fill="x", pady=1)

        # ID
        tk.Label(row, text=eid, font=("Courier", 9, "bold"), width=10,
                 bg=CARD, fg=CYAN, anchor="w").pack(side="left")
        # Type
        color_type = PURPLE if type_label == "Depouilleur" else ACCENT
        tk.Label(row, text=type_label, font=("Courier", 8), width=12,
                 bg=CARD, fg=color_type, anchor="w").pack(side="left")

        # Etat (badge coloré)
        etat_frame = tk.Frame(row, bg=CARD)
        etat_frame.pack(side="left")
        lbl_etat = tk.Label(etat_frame, text="EN ATTENTE", font=("Courier", 8, "bold"),
                             width=20, anchor="w", bg=ETATS["attente"][1],
                             fg=ETATS["attente"][2], padx=4)
        lbl_etat.pack()

        # Barre de progression (canvas simple)
        bar_frame = tk.Frame(row, bg=BORDER, height=14)
        bar_frame.pack(side="left", fill="x", expand=True, padx=(8, 8))
        bar_fill = tk.Frame(bar_frame, bg=MUTED, height=14, width=0)
        bar_fill.place(x=0, y=0, height=14)

        # Choix de vote
        lbl_vote = tk.Label(row, text="—", font=("Courier", 8, "bold"),
                            width=10, bg=CARD, fg=MUTED, anchor="w")
        lbl_vote.pack(side="right")

        self._rows[eid] = (lbl_etat, bar_frame, bar_fill, lbl_vote)

        # Mettre à jour le compteur
        nb = len(self._rows)
        self._lbl_nb_threads.config(text=f"{nb} threads actifs")

    def _set_etat(self, eid, etat_key):
        """Met à jour l'état visuel d'un thread."""
        if eid not in self._rows:
            return
        lbl_etat, bar_frame, bar_fill, lbl_vote = self._rows[eid]
        txt, bg_c, fg_c = ETATS.get(etat_key, ETATS["attente"])
        lbl_etat.config(text=txt, bg=bg_c, fg=fg_c)

        # Largeur de barre selon l'avancement
        prog = {
            "attente": 0, "reseau": 20, "verrou": 50,
            "vote_ok": 100, "double": 100, "rejet": 100,
            "termine": 100, "depoui": 40, "fusionne": 100
        }
        bar_frame.update_idletasks()
        w = bar_frame.winfo_width()
        pct = prog.get(etat_key, 0)
        fill_w = int(w * pct / 100)
        color_bar = {
            "vote_ok": GREEN, "fusionne": GREEN,
            "double": RED, "rejet": RED,
            "verrou": AMBER, "reseau": ACCENT,
            "depoui": PURPLE, "termine": MUTED, "attente": MUTED
        }.get(etat_key, MUTED)
        bar_fill.config(bg=color_bar)
        bar_fill.place(x=0, y=0, width=max(0, fill_w), height=14)

    def _set_vote(self, eid, choix):
        if eid not in self._rows:
            return
        lbl_etat, _, _, lbl_vote = self._rows[eid]
        color = COUL_CANDS.get(choix, TEXT)
        lbl_vote.config(text=choix, fg=color)

    # ── Panneau droite : compteurs + résultats + log ──
    def _build_right_panel(self, parent):
        outer = tk.Frame(parent, bg=BORDER)
        outer.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        inner = tk.Frame(outer, bg=CARD, padx=12, pady=10)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner.rowconfigure(2, weight=1)
        inner.columnconfigure(0, weight=1)

        # ── Compteurs ──
        tk.Label(inner, text="COMPTEURS LIVE", font=("Courier", 9, "bold"),
                 bg=CARD, fg=WHITE).grid(row=0, column=0, sticky="w", pady=(0, 4))
        cpt_f = tk.Frame(inner, bg=CARD)
        cpt_f.grid(row=0, column=0, sticky="ew", pady=(22, 0))

        def cpt_row(parent, label, color, row):
            tk.Label(parent, text=label, font=("Courier", 8),
                     bg=CARD, fg=MUTED).grid(row=row, column=0, sticky="w", pady=1)
            lbl = tk.Label(parent, text="0", font=("Courier", 13, "bold"),
                           bg=CARD, fg=color)
            lbl.grid(row=row, column=1, sticky="e", padx=8)
            return lbl

        self._lbl_ok     = cpt_row(cpt_f, "Votes acceptes", GREEN,  0)
        self._lbl_double = cpt_row(cpt_f, "Doubles bloques", AMBER, 1)
        self._lbl_rejet  = cpt_row(cpt_f, "Rejets",          RED,   2)

        tk.Frame(inner, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew", pady=8)

        # ── Résultats ──
        res_f = tk.Frame(inner, bg=CARD)
        res_f.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        tk.Label(res_f, text="RESULTATS", font=("Courier", 9, "bold"),
                 bg=CARD, fg=WHITE).pack(anchor="w", pady=(0, 6))

        self._bars     = {}
        self._pct_lbls = {}
        self._v_lbls   = {}
        for cand in CANDIDATS:
            col = COUL_CANDS[cand]
            blk = tk.Frame(res_f, bg=CARD)
            blk.pack(fill="x", pady=4)
            top = tk.Frame(blk, bg=CARD)
            top.pack(fill="x")
            tk.Label(top, text=cand, font=("Courier", 9, "bold"),
                     bg=CARD, fg=col).pack(side="left")
            pl = tk.Label(top, text="0%", font=("Courier", 8), bg=CARD, fg=MUTED)
            pl.pack(side="right")
            vl = tk.Label(top, text="0v", font=("Courier", 8), bg=CARD, fg=MUTED)
            vl.pack(side="right", padx=6)
            bb = tk.Frame(blk, bg=BORDER, height=12)
            bb.pack(fill="x", pady=(2, 0))
            bf = tk.Frame(bb, bg=col, height=12)
            bf.place(x=0, y=0, height=12)
            self._bars[cand]     = (bb, bf)
            self._pct_lbls[cand] = pl
            self._v_lbls[cand]   = vl

        tk.Frame(inner, bg=BORDER, height=1).grid(row=1, column=0,
                                                   sticky="ew", pady=(180, 0))

        # ── Journal ──
        tk.Label(inner, text="JOURNAL", font=("Courier", 9, "bold"),
                 bg=CARD, fg=WHITE).grid(row=2, column=0, sticky="nw", pady=(8, 0))
        log_f = tk.Frame(inner, bg=CARD)
        log_f.grid(row=2, column=0, sticky="nsew", pady=(22, 0))
        log_f.rowconfigure(0, weight=1)
        log_f.columnconfigure(0, weight=1)

        self._log = tk.Text(log_f, bg="#080c18", fg=TEXT,
                            font=("Courier", 8), relief="flat",
                            wrap="word", state="disabled", padx=6, pady=4)
        self._log.grid(row=0, column=0, sticky="nsew")
        sb2 = ttk.Scrollbar(log_f, command=self._log.yview)
        sb2.grid(row=0, column=1, sticky="ns")
        self._log.configure(yscrollcommand=sb2.set)
        self._log.tag_configure("OK",     foreground=GREEN)
        self._log.tag_configure("DOUBLE", foreground=AMBER)
        self._log.tag_configure("REJET",  foreground=RED)
        self._log.tag_configure("INFO",   foreground=ACCENT)

    # ────────────────────────────────────
    #  LANCEMENT
    # ────────────────────────────────────
    def _lancer(self):
        if self._actif:
            return
        self._reset(wipe_log=True)
        self._actif = True
        self._btn.config(state="disabled", bg=BORDER, fg=MUTED)
        self._status.config(text="Scrutin en cours...", fg=AMBER)

        nb    = self._sp_nb.get()
        pct   = self._sp_pct.get()
        delai = self._sp_delai.get() / 1000.0

        # Créer les lignes DANS le thread GUI
        for i in range(1, nb + 1):
            self._add_thread_row(f"E{i:03d}", "Electeur")
        for d in range(1, NB_DEPOUILLEURS + 1):
            self._add_thread_row(f"D{d}", "Depouilleur")

        threading.Thread(target=self._backend,
                         args=(nb, pct, delai), daemon=True).start()

    def _backend(self, nb, pct, delai_max):
        bureau = BureauDeVote(CANDIDATS, self._q.put)
        sig    = threading.Event()
        bureau.ouvrir()

        electeurs = []
        for i in range(1, nb + 1):
            double = random.randint(1, 100) <= pct
            electeurs.append(
                Electeur(f"E{i:03d}", bureau, sig, double, delai_max))

        partiaux = []
        vp = threading.Lock()
        depouilleurs = [
            Depouilleur(f"D{i+1}", bureau.urne, partiaux, vp, self._q.put)
            for i in range(NB_DEPOUILLEURS)]

        for d in depouilleurs:
            d.start()
        for e in electeurs:
            e.start()

        sig.set()   # coup d'envoi

        for e in electeurs:
            e.join()
        bureau.fermer()
        bureau.cloturer_urne()
        for d in depouilleurs:
            d.join()

        final = Counter()
        for p in partiaux:
            final.update(p)
        self._q.put(("FIN", final, nb))

    # ────────────────────────────────────
    #  POLLING
    # ────────────────────────────────────
    def _poll(self):
        try:
            while True:
                item = self._q.get_nowait()
                tag  = item[0]

                if tag == "FIN":
                    _, final, nb = item
                    self._res = final
                    self._update_bars()
                    total = sum(final.values())
                    self._status.config(
                        text=f"Termine — {total}/{nb} votes valides, "
                             f"{self._cpt['DOUBLE']} doubles rejetes",
                        fg=GREEN)
                    self._prog["value"] = 100
                    self._log_w("=" * 38 + " FIN DU SCRUTIN", "INFO")
                    self._actif = False
                    self._btn.config(state="normal", bg=ACCENT, fg=BG)

                elif tag == "ETAT":
                    _, eid, etat = item
                    self._set_etat(eid, etat)

                elif tag == "VOTE":
                    _, eid, choix = item
                    self._set_vote(eid, choix)
                    self._res[choix] += 1
                    self._update_bars()

                elif tag == "LOG":
                    _, kind, msg = item
                    if kind in self._cpt:
                        self._cpt[kind] += 1
                    self._lbl_ok.config(    text=str(self._cpt["OK"]))
                    self._lbl_double.config(text=str(self._cpt["DOUBLE"]))
                    self._lbl_rejet.config( text=str(self._cpt["REJET"]))
                    icons = {"OK": "[OK]   ", "DOUBLE": "[DBL]  ",
                             "REJET": "[REJ]  ", "INFO":   "[INFO] "}
                    self._log_w(icons.get(kind, "       ") + msg, kind)
                    done = sum(self._cpt.values())
                    nb   = max(self._sp_nb.get(), 1)
                    self._prog["value"] = min(99, done / nb * 100)

        except Empty:
            pass
        self.after(30, self._poll)

    def _update_bars(self):
        total = sum(self._res.values())
        if total == 0:
            return
        for cand in CANDIDATS:
            nb  = self._res.get(cand, 0)
            pct = nb / total * 100
            bb, bf = self._bars[cand]
            bb.update_idletasks()
            w = bb.winfo_width()
            bf.place(x=0, y=0, width=max(0, int(w * pct / 100)), height=12)
            self._pct_lbls[cand].config(text=f"{pct:.0f}%")
            self._v_lbls[cand].config(  text=f"{nb}v")

    def _log_w(self, msg, tag="INFO"):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    # ────────────────────────────────────
    #  RESET
    # ────────────────────────────────────
    def _reset(self, wipe_log=False):
        if self._actif:
            return
        self._cpt  = {"OK": 0, "DOUBLE": 0, "REJET": 0}
        self._res  = Counter()
        self._rows = {}
        for w in self._threads_container.winfo_children():
            w.destroy()
        self._lbl_nb_threads.config(text="0 threads actifs")
        self._lbl_ok.config(text="0")
        self._lbl_double.config(text="0")
        self._lbl_rejet.config(text="0")
        self._prog["value"] = 0
        self._status.config(text="En attente...", fg=MUTED)
        for cand in CANDIDATS:
            _, bf = self._bars[cand]
            bf.place(x=0, y=0, width=0, height=12)
            self._pct_lbls[cand].config(text="0%")
            self._v_lbls[cand].config(  text="0v")
        if wipe_log:
            self._log.config(state="normal")
            self._log.delete("1.0", "end")
            self._log.config(state="disabled")
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except Empty:
                break
        self._btn.config(state="normal", bg=ACCENT, fg=BG)


if __name__ == "__main__":
    app = VoteApp()
    app.mainloop()
