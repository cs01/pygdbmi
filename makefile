# run pip install -r dev_requirements.txt before running make test
.PHONY: test publish

test: functional_test style_test readme_test

functional_test:
	python setup.py test

readme_test:
	python setup.py checkdocs

style_test:
	flake8 pygdbmi --ignore E501,E127,E128

publish: test
	python setup.py upload
