# nanoregex — charter done-criterion #4: `make check` from a clean clone.

PY ?= python3

.PHONY: check test bench fuzz smoke clean

check:
	$(PY) -m compileall -q nanoregex tests tools bench
	$(PY) -m unittest discover -s tests -q
	$(PY) bench/run_bench.py --smoke

test:
	$(PY) -m unittest discover -s tests -q

bench:
	$(PY) bench/run_bench.py

fuzz:
	$(PY) tools/fuzz_diff.py --cases 5000

clean:
	find . -name __pycache__ -type d -exec rm -rf {} +
