$ErrorActionPreference = 'Stop'
$reportRoot = $PSScriptRoot
$buildDir = Join-Path $reportRoot 'build'
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

Push-Location $reportRoot
try {
    & pdflatex --enable-installer -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "Initial pdflatex pass failed with exit code $LASTEXITCODE." }

    Push-Location $buildDir
    try {
        $env:BIBINPUTS = '..;'
        & bibtex main
        if ($LASTEXITCODE -ne 0) { throw "BibTeX failed with exit code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
    }

    & pdflatex --enable-installer -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "Second pdflatex pass failed with exit code $LASTEXITCODE." }
    & pdflatex --enable-installer -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=build main.tex
    if ($LASTEXITCODE -ne 0) { throw "Final pdflatex pass failed with exit code $LASTEXITCODE." }
}
finally {
    Pop-Location
}

Write-Host "Built: $(Join-Path $buildDir 'main.pdf')"

