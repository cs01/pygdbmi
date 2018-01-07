# run pip install -r dev_requirements.txt before running make test
.PHONY: test upload clean

test: functional_test style_test readme_test

functional_test:
	python setup.py test

readme_test:
	python setup.py checkdocs

style_test:
	flake8 pygdbmi --ignore E501,E127,E128

publish: test clean
	python setup.py sdist bdist_wheel --universal
	twine upload dist/*

testpublish: test clean
	python setup.py sdist bdist_wheel --universal
	twine upload dist/* -r pypitest

clean:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	rm -rf dist build
	make -C ./pygdbmi/docs clean

docs:
	make -C ./pygdbmi/docs
