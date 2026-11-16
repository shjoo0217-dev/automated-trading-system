$ErrorActionPreference = 'Stop'
# Run from the directory containing investment_dataset; requires Python 3.12.
py -3.12 -m venv .star-venv
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
& .\.star-venv\Scripts\python.exe -m pip install -r investment_dataset/pipeline/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$env:PYTHONPATH = 'investment_dataset/pipeline'
& .\.star-venv\Scripts\python.exe investment_dataset/pipeline/run_direct.py --state investment_dataset/data/checkpoint.json --max-cycles 5 --posts-per-cycle 60
if ($LASTEXITCODE -ne 0) { throw 'Pipeline stopped; checkpoint retained for resume' }
