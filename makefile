# run pip install -r dev_requirements.txt before running make test
.PHONY: test upload clean

test: functional_test style_test readme_test

functional_test:
	python setup.py test

readme_test:
	python setup.py checkdocs

style_test:
	flake8 pygdbmi --ignore E501,E127,E128

upload:
	python setup.py upload

testupload: test
	rm -rf dist
	python setup.py sdist bdist_wheel --universal
	twine upload dist/* -r pypitest

clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	make -C ./pygdbmi/docs clean

docs:
	make -C ./pygdbmi/docs
