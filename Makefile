
# Makefile used to install tubular at the beginning of a pipeline job.
# A 'make install_venv' should be the first task in your job.
#
# If TUBULAR_HASH environment variable is non-empty, it uses the tubular repo at that hash.
# If TUBULAR_HASH environment variable is empty, it checks for a TUBULAR_BRANCH variable.
# If TUBULAR_BRANCH is non-empty, it checks out the HEAD of that branch.
# If both variables are empty, it uses the material's version.


VENV_NAME=go-agent-venv
TUBULAR_MATERIAL_PATH=/var/lib/go-agent/pipelines/$(GO_PIPELINE_NAME)/tubular

tubular_install:
	@echo "Installing tubular requirements..."
	cd $(TUBULAR_MATERIAL_PATH)
ifeq ($(strip $(TUBULAR_HASH)),)
# If TUBULAR_HASH is empty, check for a branch.
ifneq ($(strip $(TUBULAR_BRANCH)),)
# If TUBULAR_BRANCH is non-empty, check out the branch.
	git checkout -t origin/$(TUBULAR_BRANCH)
endif
else
# TUBULAR_HASH was non-empty, so update repo to that hash.
	git reset $(TUBULAR_HASH)
endif
	pip install -r requirements.txt
	pip install .

destroy_venv:
	@echo "Destroying virtualenv..."
	$(shell deactivate)
	cd ~
	rm -rf $(VENV_NAME)

ifndef IN_VENV
install_venv:
	@echo "Making virtualenv..."
	cd ~
	virtualenv $(VENV_NAME)
	./source_venv.sh $(MAKE) install_venv
else
install_venv: tubular_install
endif

uninstall_venv: destroy_venv
	@echo "make uninstall_venv..."

install: tubular_install
	@echo "make install..."
