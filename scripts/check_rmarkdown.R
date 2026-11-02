# Render every R Markdown document and syntax-check every chunk.
#
# Without credentials, bskyr can't call the API, so most documents knit
# "prose-only" (their API chunks are skipped). Part 05 is the exception: it
# analyzes the shared archive, so its whole analysis runs, including a check
# that R reproduces the Python notebook's regression coefficients. Part 10's
# Jetstream chunks also run, because Jetstream needs no credentials.
#
# Usage (from the repository root):  Rscript scripts/check_rmarkdown.R

files <- list.files("RMarkdown", pattern = "\\.Rmd$", recursive = TRUE, full.names = TRUE)
out_dir <- file.path(tempdir(), "rendered")
dir.create(out_dir, showWarnings = FALSE)

failures <- 0
for (f in files) {
  parsed <- tryCatch({
    parse(knitr::purl(f, output = tempfile(fileext = ".R"), quiet = TRUE, documentation = 0))
    "parse ok"
  }, error = function(e) paste("PARSE FAIL:", conditionMessage(e)))

  knit <- tryCatch({
    rmarkdown::render(f, output_dir = out_dir, intermediates_dir = out_dir,
                      knit_root_dir = dirname(normalizePath(f)), quiet = TRUE)
    "knit ok"
  }, error = function(e) paste("KNIT FAIL:", conditionMessage(e)))

  ok <- parsed == "parse ok" && knit == "knit ok"
  if (!ok) failures <- failures + 1
  cat(sprintf("[%s] %s: %s, %s\n", if (ok) "ok" else "FAIL", basename(f), parsed, knit))
}

# Knitting writes data/ next to some documents; R outputs are never committed
unlink(list.files("RMarkdown", pattern = "^data$", recursive = TRUE,
                  include.dirs = TRUE, full.names = TRUE), recursive = TRUE)

if (failures > 0) quit(status = 1)
