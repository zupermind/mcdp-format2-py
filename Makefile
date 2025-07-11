

generate:
	# $(MAKE) -C ../mcdp-formats preprocess
	cargo run -p zuper-rs-schemas --bin zuper-rs-schemas -- python  \
		--schema ../../mcdp-formats/out/schema-no-concrete.yaml \
		--target src/mcdp_format2_py/schemas.py
