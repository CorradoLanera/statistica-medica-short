source("renv/activate.R")
Sys.setenv(GITHUB_PAT = gitcreds::gitcreds_get()$password)

if (interactive()) {
  suppressPackageStartupMessages(suppressWarnings({
    library(devtools)
    library(usethis)
  }))
}
