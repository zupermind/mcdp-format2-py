all:
	@echo

out=out
tested_packages := mcdp_format2_py
deployed_packages := mcdp_format2_py
test_environment := DISABLE_CONTRACTS=1

ifneq ($(filter contracts,$(deployed_packages)),)
test_environment :=
endif

.PHONY: all template bump upload black install-deps install-testing-deps test coverage-combine docs


template:
	zuper-cli template

bump:
	zuper-cli bump

upload:
	zuper-cli upload

black:
	black -l 110 --target-version py312 src

install-deps:
	pip3 install --user shyaml
	shyaml get-values install_requires < project.pp1.yaml > .requirements.txt
	pip3 install --user --upgrade -r .requirements.txt
	rm .requirements.txt

install-testing-deps:
	pip3 install --user shyaml
	shyaml get-values tests_require < project.pp1.yaml > .requirements_tests.txt
	pip3 install --user --upgrade -r .requirements_tests.txt
	rm .requirements_tests.txt

	pip install \
		pipdeptree\
		bumpversion\
		nose2\
		nose2-html-report\
		pre-commit\
		coverage\
		codecov\
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

# sigil 2406de0482d2214e656f648d0470e7a0
# template-meta template-version=1.8.7
# template-meta zuper-templating-version=8.25.2901010000
