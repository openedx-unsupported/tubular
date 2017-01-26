
# Makefile used to run tests.

unittest:
# command to run tests, the -n auto will run tests in
# parallel with as many cores as are available.
	tox -e py{27,34,35}-test

quality:
	tox -e py{27,34,35}-quality

test: unittest quality
