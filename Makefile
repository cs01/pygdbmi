.PHONY: test clean

test:
	python setup.py test

clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	make -C ./pygdbmi/docs clean

docs:
	make -C ./pygdbmi/docs

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  test    to run tests"
	@echo "  clean   to clean temporary files"
	@echo "  docs    to generate documentation"
