# Render every R Markdown document and syntax-check every chunk.
#
# Two modes:
#
#   Rscript scripts/check_rmarkdown.R
#     The student path: no credentials, so bskyr can't call the API and most
#     documents knit "prose-only" (their API chunks are skipped). Part 05 still
#     runs its whole analysis on the shared archive, including a check that R
#     reproduces the Python notebook's coefficients; Part 10's Jetstream chunks
#     run too, because Jetstream needs no credentials.
#
#   Rscript scripts/check_rmarkdown.R --mock-api
#     Runs the API chunks too, without credentials, through the mock API in
#     RMarkdown/tests/mock_api.R: login returns a fake session, reads go to the
#     public AppView, and any write request fails the check. This is what tests
#     the code that calls bskyr (issue #8).
#
# Optionally name documents to check (default: all), e.g.
#   Rscript scripts/check_rmarkdown.R --mock-api "Part 02"

args <- commandArgs(trailingOnly = TRUE)
mock <- "--mock-api" %in% args
patterns <- setdiff(args, "--mock-api")

files <- list.files("RMarkdown", pattern = "\\.Rmd$", recursive = TRUE, full.names = TRUE)
if (length(patterns)) {
  files <- files[Reduce(`|`, lapply(patterns, function(p) grepl(p, files, fixed = TRUE)))]
}
if (mock) source("RMarkdown/tests/mock_api.R")

# Rendered documents go to a temporary directory, or to RENDER_DIR if set
out_dir <- Sys.getenv("RENDER_DIR", file.path(tempdir(), "rendered"))
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

render_one <- function(f) {
  rmarkdown::render(f, output_dir = out_dir, intermediates_dir = out_dir,
                    knit_root_dir = dirname(normalizePath(f)), quiet = TRUE,
                    envir = new.env(parent = globalenv()))
}

cat(if (mock) "Mode: mock API (API chunks execute against public data)\n"
    else "Mode: no credentials (API chunks skipped)\n")
failures <- 0
for (f in files) {
  parsed <- tryCatch({
    parse(knitr::purl(f, output = tempfile(fileext = ".R"), quiet = TRUE, documentation = 0))
    "parse ok"
  }, error = function(e) paste("PARSE FAIL:", conditionMessage(e)))

  knit <- tryCatch({
    if (mock) with_bsky_mock(render_one(f)) else render_one(f)
    "knit ok"
  }, error = function(e) paste("KNIT FAIL:", conditionMessage(e)))

  ok <- parsed == "parse ok" && knit == "knit ok"
  if (!ok) failures <- failures + 1
  cat(sprintf("[%s] %s: %s, %s\n", if (ok) "ok" else "FAIL", basename(f), parsed, knit))
}

# Knitting writes data/ next to some documents; R outputs are never committed.
# Remove only the checked documents' data/, so parallel checks don't collide.
# (Part 00 sits at RMarkdown/ itself, whose data/ is never written.)
part_dirs <- setdiff(unique(dirname(files)), "RMarkdown")
unlink(file.path(part_dirs, "data"), recursive = TRUE)

if (failures > 0) quit(status = 1)
