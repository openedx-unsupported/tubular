
# Makefile used to run tests.

unittest:
# command to run tests, the -n auto will run tests in
# parallel with as many cores as are available.
	pytest -n auto

quality:
	pep8 --config=.pep8 tubular scripts admin
	pylint tubular
	pylint scripts
	pylint admin

test: unittest quality

