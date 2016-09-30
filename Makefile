
# Makefile used to run tests.

unittest:
# command to run tests, the --process=-1 will run tests in
# parallel with as many cores as are available.
	nosetests --processes=-1

quality:
	pep8 --config=.pep8 tubular scripts admin
	pylint tubular
	pylint scripts
	pylint admin

test: unittest quality

