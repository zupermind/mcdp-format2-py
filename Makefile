
all:
	make preprocess
	make generate
	make test

preprocess:
	make -C ../../mcdp-formats/ preprocess

the_schema=../../mcdp-formats/out/schema-no-concrete.yaml

generate:
	# $(MAKE) -C ../mcdp-formats preprocess
	cargo run -p zuper-rs-schemas --bin zuper-rs-schemas -- python  \
		--schema $(the_schema) \
		--target src/mcdp_format2_py/schemas.py
	cp ${the_schema} mcdp2-openapi-schema.yaml

	echo Now you need to update the version in pyproject.toml and mcdp_format2_py/__init__.py

test:
	nose2 mcdp_format2_py.schemas


upload:
	rm -rf dist build
	python -m build
	twine upload dist/*
