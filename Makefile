
# Makefile used to run tests.

unittest:
# command to run tests, the -n auto will run tests in
# parallel with as many cores as are available.
	tox

quality:
	tox -- -m pylint

test:
	tox

upgrade:
	pip install -qr pip-tools.txt
	pip-compile -v --no-emit-trusted-host --no-index --rebuild --upgrade pip-tools.in
	pip-compile -v --no-emit-trusted-host --no-index --rebuild --upgrade requirements.in
