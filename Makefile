
# Makefile used to run tests.

unittest:
# command to run tests, the -n auto will run tests in
# parallel with as many cores as are available.
	tox

quality:
	pep8 --config=.pep8 tubular scripts admin
	pylint --py3k tubular
	pylint --py3k scripts
	pylint --py3k admin
	pylint tubular
	pylint scripts
	pylint admin

test: unittest quality
