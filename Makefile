
all:
	make preprocess
	make generate
	make test
	
preprocess:
	make -C ../../mcdp-formats/ preprocess	

generate:
	# $(MAKE) -C ../mcdp-formats preprocess
	cargo run -p zuper-rs-schemas --bin zuper-rs-schemas -- python  \
		--schema ../../mcdp-formats/out/schema-no-concrete.yaml \
		--target src/mcdp_format2_py/schemas.py

test:
	nose2 mcdp_format2_py.schemas


upload:
	rm -rf dist
	python setup.py sdist bdist_wheel
	twine upload dist/*