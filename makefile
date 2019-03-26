# run pip install -r dev_requirements.txt before running make test
.PHONY: test upload clean docs

test:
	python -m tests

clean:
	rm -rf dist build *.egg-info
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

build: clean
	python -m pip install --upgrade --quiet setuptools wheel twine
	python setup.py --quiet sdist bdist_wheel
	twine check dist/*

publish: test build
	twine upload dist/*

testpublish: test clean
	python setup.py sdist bdist_wheel --universal
	twine upload dist/* -r pypitest

docs:
	make -C ./doc_generation
