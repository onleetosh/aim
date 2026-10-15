# Common tasks for A.I.M. Run `make help` to list them.
# Works on Windows (GNU make, e.g. `winget install ezwinports.make`) and macOS/Linux.

ifeq ($(OS),Windows_NT)
  VENV_PYTHON := .venv/Scripts/python.exe
  SYSTEM_PYTHON ?= python
else
  VENV_PYTHON := .venv/bin/python
  SYSTEM_PYTHON ?= python3
endif

PORT ?= 5000

.PHONY: help venv install run prod check clean

help:
	@echo "make install  Create .venv and install dependencies"
	@echo "make run      Start the dev server at http://localhost:$(PORT)"
	@echo "make prod     Start with gunicorn, as Render does (macOS/Linux only)"
	@echo "make check    Compile-check the Python and JavaScript sources"
	@echo "make clean    Remove caches (keeps your database)"

$(VENV_PYTHON):
	$(SYSTEM_PYTHON) -m venv .venv

venv: $(VENV_PYTHON)

install: $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install -r requirements.txt

run: install
	$(VENV_PYTHON) -m flask --app app run --debug --port $(PORT)

# gunicorn does not run on Windows; Render uses this same command.
prod: install
	$(VENV_PYTHON) -m gunicorn app:app --bind 0.0.0.0:$(PORT)

check: install
	$(VENV_PYTHON) -m compileall -q app.py backend
	node --check frontend/js/main.js
	node --check frontend/js/auth.js

clean:
	$(VENV_PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if '.venv' not in p.parts]"
