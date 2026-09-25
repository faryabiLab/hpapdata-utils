library(readr)

# Paths are relative: run this script from inside the calculate_perifusion/ folder.
input_dir  <- "perifusion_input_files"
output_dir <- "perifusion_output_files"

# SQL file is named by run date (YYMMDD), e.g. add_perifusion_calc_260925.sql.
# NOTE: it is emptied at the start of every run, so a second run on the same
# day overwrites that day's SQL file.
sql_file   <- paste0("add_perifusion_calc_", format(Sys.Date(), "%y%m%d"), ".sql")

# Data folders are gitignored, so create them if missing (e.g. fresh clone).
dir.create(input_dir,  showWarnings = FALSE)
dir.create(output_dir, showWarnings = FALSE)

writeLines(character(0), sql_file)

r_to_sql_col <- function(r_name) {
  sql_name <- gsub("\\)", "", gsub("\\(", "_", r_name))
  sql_name <- tolower(sql_name)
  substr(sql_name, 1, 1) <- toupper(substr(sql_name, 1, 1))
  sql_name
}

input_files <- list.files(input_dir, pattern = "_Perifusion_data\\.csv$", full.names = TRUE)

for (filepath in input_files) {
  filename  <- basename(filepath)
  donor_id  <- sub("_Perifusion_data\\.csv$", "", filename)
  out_file  <- file.path(output_dir, paste0(donor_id, "_Perifusion_summary_with_inputs.csv"))

  if (file.exists(out_file)) {
    message("Skipping ", donor_id, ": output already exists")
    next
  }

  tryCatch({
    df <- read_csv(filepath, show_col_types = FALSE)

    df$INSULIN_PER_100_ISLETS  <- as.numeric(df$INSULIN_PER_100_ISLETS)
    df$GLUCAGON_PER_100_ISLETS <- as.numeric(df$GLUCAGON_PER_100_ISLETS)

    stimuli <- list(
      aam   = list(base = 6:10,    test = 11:41),
      Glu3  = list(base = 37:41,   test = 42:61),
      G16.7 = list(base = 57:61,   test = 62:81),
      ibmx  = list(base = 77:81,   test = 82:101),
      kcl   = list(base = 117:121, test = 122:nrow(df))
    )

    results <- c()

    for (stim in names(stimuli)) {
      b <- stimuli[[stim]]$base
      t <- stimuli[[stim]]$test

      ins_base  <- df$INSULIN_PER_100_ISLETS[b]
      ins_test  <- df$INSULIN_PER_100_ISLETS[t]
      gluc_base <- df$GLUCAGON_PER_100_ISLETS[b]
      gluc_test <- df$GLUCAGON_PER_100_ISLETS[t]

      i_auc <- sum(ins_test)  - mean(ins_base) * length(ins_test)
      i_si  <- max(ins_test)  / mean(ins_base)

      g_auc <- sum(gluc_test) - mean(gluc_base) * length(gluc_test)
      g_si  <- if (stim %in% c("Glu3", "G16.7")) {
        min(gluc_test) / mean(gluc_base)
      } else {
        max(gluc_test) / mean(gluc_base)
      }

      results[paste0("I_AUC(", stim, ")")] <- i_auc
      results[paste0("I_SI(",  stim, ")")]  <- i_si
      results[paste0("G_AUC(", stim, ")")] <- g_auc
      results[paste0("G_SI(",  stim, ")")]  <- g_si
    }

    for (metric_name in names(results)) {
      df[[metric_name]] <- NA
      df[[metric_name]][1] <- results[[metric_name]]
    }

    write_csv(df, out_file, na = "")

    # SQL INSERT — only include metrics that are not NA
    valid  <- results[!is.na(results)]
    if (length(valid) > 0) {
      cols <- paste0("`", c("donor_ID", sapply(names(valid), r_to_sql_col)), "`", collapse = ", ")
      vals <- paste0("'", c(donor_id,   as.character(valid)),                "'", collapse = ", ")
      sql  <- paste0("INSERT INTO `hpap_records`.`perifusion_calculated_values` (", cols, ") VALUES (", vals, ");")
      cat(sql, "\n", file = sql_file, append = TRUE)
    }

    message("Done: ", donor_id)

  }, error = function(e) {
    message("ERROR processing ", donor_id, ": ", conditionMessage(e))
  })
}
