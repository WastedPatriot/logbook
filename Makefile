.PHONY: site check

site:
	python3 scripts/build.py

check:
	python3 scripts/build.py --self-test
	python3 scripts/build.py
