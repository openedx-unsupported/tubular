
# Makefile used to run tests.

unittest:
# command to run tests, the -n auto will run tests in
# parallel with as many cores as are available.
	tox

quality:
	tox -- -m pylint

test:
	tox

# Define PIP_COMPILE_OPTS=-v to get more information during make upgrade.
PIP_COMPILE = pip-compile --upgrade $(PIP_COMPILE_OPTS)

upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade:
	pip install -qr requirements/pip-tools.txt
	$(PIP_COMPILE) --allow-unsafe --rebuild --upgrade -o requirements/pip.txt requirements/pip.in
	$(PIP_COMPILE) --rebuild --upgrade -o requirements/pip-tools.txt requirements/pip-tools.in
	$(PIP_COMPILE) --rebuild --upgrade -o requirements/base.txt requirements/base.in
	$(PIP_COMPILE) --rebuild --upgrade -o requirements/testing.txt requirements/testing.in
