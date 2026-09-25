# calculate_perifusion

R script for batch processing perifusion time-series data from HPAP donors. Computes insulin and glucagon secretion metrics (area under the curve and stimulation index) across five stimulus phases, and generates:

- one output CSV per donor, and
- one `.sql` file of `INSERT` statements for loading the metrics into the `hpap_records` MySQL database.

---

## Requirements

- R (4.0 or higher)
- R package: [`readr`](https://readr.tidyverse.org/)

Install the required package in R:

```r
install.packages("readr")
```

---

## Input

Place donor perifusion CSV files in the `perifusion_input_files/` folder. Each file must follow the naming convention:

```
HPAP-XXX_Perifusion_data.csv
```

Expected columns:

| Column | Description |
|---|---|
| `TIME` | Time point (minutes) |
| `STIMULUS` | Stimulus applied at that time point |
| `INSULIN_PER_100_ISLETS` | Insulin secretion per 100 islets |
| `GLUCAGON_PER_100_ISLETS` | Glucagon secretion per 100 islets |
| `ISLET_NUMBER` | Number of islets (first row only) |
| `DNA_CONTENT` | DNA content (first row only) |
| `INSULIN_CONTENT` | Insulin content (first row only) |
| `GLUCAGON_CONTENT` | Glucagon content (first row only) |

The `perifusion_input_files/` and `perifusion_output_files/` folders are gitignored. The script creates them if they don't exist (e.g. in a fresh clone).

---

## Usage

Paths in the script are relative, so run it from inside the `calculate_perifusion/` folder:

```bash
cd calculate_perifusion
Rscript calc_and_csv_perifusion.R
```

The script processes all `*_Perifusion_data.csv` files in `perifusion_input_files/` and prints progress to the console:

```
Done: HPAP-150
Done: HPAP-151
Skipping HPAP-152: output already exists
ERROR processing HPAP-XXX: <error message>
```

---

## Output

### Output CSV (one per donor)

Written to `perifusion_output_files/`:

```
HPAP-XXX_Perifusion_summary_with_inputs.csv
```

Contains the donor's input data with the metric columns added (e.g. `I_AUC(aam)`, `G_SI(kcl)`). Metric values are in the first row; the rest of those columns are blank. This file is a local working copy and is also what the script uses to skip donors already processed (see [Script behavior](#script-behavior)).

### SQL file (one per run)

Written to the `calculate_perifusion/` folder, named by the run date (`YYMMDD`):

```
add_perifusion_calc_<YYMMDD>.sql
```

Contains one `INSERT` per processed donor into `` `hpap_records`.`perifusion_calculated_values` ``, e.g. (truncated):

```sql
INSERT INTO `hpap_records`.`perifusion_calculated_values` (`donor_ID`, `I_auc_aam`, `I_si_aam`, `G_auc_aam`, `G_si_aam`, ..., `G_si_kcl`) VALUES ('HPAP-177', '-7.61541719999999', '1.57072307207172', ...);
```

Metric names are converted to SQL column names by replacing `(` with `_`, removing `)`, and lowercasing everything except the first letter (e.g. `I_AUC(G16.7)` → `I_auc_g16.7`).

### Computed metrics (per stimulus phase)

Five stimulus phases: `aam`, `Glu3`, `G16.7`, `ibmx`, `kcl`

| Metric | Formula |
|---|---|
| `I_AUC` | `sum(insulin_test) - mean(insulin_base) × n_test` |
| `I_SI` | `max(insulin_test) / mean(insulin_base)` |
| `G_AUC` | `sum(glucagon_test) - mean(glucagon_base) × n_test` |
| `G_SI` | `min(glucagon_test) / mean(glucagon_base)` for Glu3 and G16.7; `max / mean` for all others |

Baseline and test periods are fixed **row ranges** in the script (not read from the `STIMULUS` column):

| Phase | Base rows | Test rows |
|---|---|---|
| `aam` | 6–10 | 11–41 |
| `Glu3` | 37–41 | 42–61 |
| `G16.7` | 57–61 | 62–81 |
| `ibmx` | 77–81 | 82–101 |
| `kcl` | 117–121 | 122–last row |

Negative AUC values, and glucagon SI below 1 for `Glu3`/`G16.7`, are expected results of these formulas.

---

## Script behavior

- **Skips existing outputs** — if an output CSV already exists for a donor in `perifusion_output_files/`, that donor is skipped and gets no `INSERT`. Delete the output CSV to reprocess.
- **SQL file is emptied at the start of every run** — a second run on the same day overwrites that day's `.sql` file. Load the SQL into MySQL before re-running.
- **Reprocessing a donor already in the database** generates a new `INSERT` for that donor. The existing row in `perifusion_calculated_values` must be handled separately before loading.
- **Fixed row ranges** — if a donor's file has a different number of time points or a different protocol, the metrics will be wrong without any error. Check the row count against a previous donor if in doubt.
- **Error handling** — if a file fails to process, an error message is printed and the script continues to the next file.
- **NA handling** — metrics that cannot be computed (e.g. missing glucagon data) are written as blank cells in the output CSV and left out of the `INSERT`.

---

## Related resources

- [HPAP (Human Pancreas Analysis Program)](https://hpap.pmacs.upenn.edu/)
- [faryabiLab](https://github.com/faryabiLab)
