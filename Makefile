all:
	@echo

out=out
tested_packages := mcdp_format2_py
deployed_packages := mcdp_format2_py
test_environment := DISABLE_CONTRACTS=1

ifneq ($(filter contracts,$(deployed_packages)),)
test_environment :=
endif

.PHONY: all template bump upload black install-deps install-testing-deps install-local-tools test coverage-combine docs


template:
	zuper-templating template

bump:
	zuper-cli bump

upload:
	zuper-cli upload

black:
	black -l 110 --target-version py312 src

install-deps:
	python3 -m pip install --user shyaml
	shyaml get-values install_requires < project.pp1.yaml > .requirements.txt
	python3 -m pip install --user --upgrade -r .requirements.txt
	rm .requirements.txt

install-testing-deps: install-local-tools
	shyaml get-values tests_require < project.pp1.yaml > .requirements_tests.txt
	python3 -m pip install --user --upgrade -r .requirements_tests.txt
	rm .requirements_tests.txt

# Developer bootstrap; generated CI uses the tools already in its image.
install-local-tools:
	python3 -m pip install --user \
		shyaml\
		pipdeptree\
		bumpversion\
		nose2\
		nose2-html-report\
		pre-commit\
		coverage\
		codecov-cli==11.3.1\
		sphinx\
		sphinx-rtd-theme

test:
	$(test_environment) python -m nose2 -v $(tested_packages)

coverage-combine:
	coverage combine

ifneq (,)
docs:
	$(MAKE) -C docs
else
docs:
	sphinx-build src $(out)/docs
endif

-include extra.mk

# sigil 96b258f227c46095bc1fa639d3e4bf0d
# template-meta template-version=2.6
# template-meta zuper-templating-version=16.9.2610181445
