
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
PIP_COMPILE = pip-compile --no-emit-trusted-host --rebuild --upgrade  $(PIP_COMPILE_OPTS)

COMMON_CONSTRAINTS_TXT=requirements/common_constraints.txt
.PHONY: $(COMMON_CONSTRAINTS_TXT)
$(COMMON_CONSTRAINTS_TXT):
	wget -O "$(@)" https://raw.githubusercontent.com/edx/edx-lint/master/edx_lint/files/common_constraints.txt || touch "$(@)"

upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade: $(COMMON_CONSTRAINTS_TXT)  ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -qr requirements/pip-tools.txt
	$(PIP_COMPILE) --allow-unsafe -o requirements/pip.txt requirements/pip.in
	$(PIP_COMPILE) -o requirements/pip-tools.txt requirements/pip-tools.in
	pip install -qr requirements/pip.txt
	pip install -qr requirements/pip-tools.txt
	$(PIP_COMPILE) -o requirements/base.txt requirements/base.in
	$(PIP_COMPILE) -o requirements/testing.txt requirements/testing.in
