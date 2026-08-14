.PHONY: regenerate preprocess generate test-schema-import pre-circle-tests upload-twine

all: regenerate

regenerate: preprocess generate test-schema-import

preprocess:
	$(MAKE) -C ../../mcdp-formats/ preprocess

the_schema = ../../mcdp-formats/out/schema-no-concrete.yaml

generate:
	cargo run -p zuper-rs-schemas --bin zuper-rs-schemas -- python \
		--schema $(the_schema) \
		--target src/mcdp_format2_py/schemas.py
	cp $(the_schema) mcdp2-openapi-schema.yaml
	@echo Now you need to update the version in pyproject.toml and src/mcdp_format2_py/__init__.py

test-schema-import:
	python -m nose2 -v mcdp_format2_py.schemas

pre-circle-tests: test-schema-import

upload-twine:
	rm -rf dist build
	python -m build
	twine upload dist/*
