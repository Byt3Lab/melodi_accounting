# MELODI Accounting — Directives du Module Comptabilité Générales (`modules/melodi_accounting/`)

Le module `melodi_accounting` gère le plan comptable, le journal général, les écritures comptables (débit/crédit), les exercices comptables et l'automatisation comptable découlant des ventes, achats et opérations de trésorerie.

---

## 1. Modèles et Schéma de Données

- **`AccountModel`** (`ml_acc_accounts`) : Plan comptable général (`account_number`, `name`, `type`, `parent_id`, `balance`).
- **`JournalModel`** (`ml_acc_journals`) : Journaux comptables (`code`: `VT` Ventes, `AC` Achats, `BQ` Banque, `CA` Caisse, `OD` Opérations Diverses).
- **`MoveModel`** (`ml_acc_moves`) : Pièces comptables (`move_id`, `journal_id`, `date`, `ref`, `state`: `'draft'` / `'posted'`).
- **`MoveLineModel`** (`ml_acc_move_lines`) : Écritures comptables individuelles (`account_id`, `debit`, `credit`, `partner_id`, `reconciled`).
- **`FiscalYearModel`** (`ml_acc_fiscal_years`) : Périodes et exercices comptables.

---

## 2. Principes Comptables Impératifs

1. **Équilibre Strict Débit / Crédit** :
   Une pièce comptable (`MoveModel`) ne peut passer à l'état comptabilisé (`posted`) que si la somme totale des débits est exactement égale à la somme totale des crédits ($\sum \text{debit} = \sum \text{credit}$).
2. **Immutabilité des Écritures Comptabilisées** :
   Une fois une pièce passée à l'état `'posted'`, ses lignes d'écriture (`MoveLineModel`) ne doivent **jamais** être modifiées ni supprimées directement. Une annulation nécessite une pièce d'extourne (écriture d'inversion).
3. **Automatisation via Événements Inter-Modules** :
   Le module s'abonne aux événements des autres modules via des écouteurs déclarés dans `load()` :
   ```python
   # S'abonner aux factures validées pour générer l'écriture comptable automatique
   self.add_event_listener("melodi_invoicing", "invoice_posted", self.on_invoice_posted)
   self.add_event_listener("melodi_retail", "sale_completed", self.on_retail_sale_completed)
   ```
4. **Journaux et Rapprochement** :
   Le rapprochement comptable s'effectue en associant des `move_line_id` de même compte auxiliaire dont le solde est nul.
