PYTHON ?= python3
TEST_ARGS ?= discover -s tests
SPREAD_SCRIPT := scripts/spread_codex_caveman.py
SPREAD_DIRS ?=

.PHONY: info test check-spread-dirs codex_spread_dry_run codex_spread

info:
	@printf '\033[1;36m%s\033[0m\n' 'caveman Makefile help'
	@printf '\033[2m%s\033[0m\n' 'Quick commands for tests and Codex spread.'
	@printf '\n\033[1;33m%s\033[0m\n' 'Commands'
	@printf '  \033[1mmake test\033[0m\n'
	@printf '  \033[1mmake test TEST_ARGS="tests.test_codex_spread"\033[0m\n'
	@printf '  \033[1mmake codex_spread_dry_run SPREAD_DIRS="/Users/username/dev /Users/username/work"\033[0m\n'
	@printf '  \033[1mmake codex_spread SPREAD_DIRS="/Users/username/dev /Users/username/work"\033[0m\n'
	@printf '\n\033[1;32m%s\033[0m\n' 'What each command does'
	@printf '  \033[1mtest\033[0m                  Run Python unit tests.\n'
	@printf '  \033[1mcodex_spread_dry_run\033[0m  Show what spread script would change.\n'
	@printf '  \033[1mcodex_spread\033[0m          Apply spread changes to target repos.\n'
	@printf '\n\033[1;35m%s\033[0m\n' 'How to pass directories'
	@printf '  Use \033[1mSPREAD_DIRS\033[0m with paths separated by spaces.\n'
	@printf '  Example: \033[1mSPREAD_DIRS="/Users/username/dev /Users/username/work"\033[0m\n'
	@printf '\n\033[1;31m%s\033[0m\n' 'Common mistake'
	@printf '  \033[31mWrong:\033[0m \033[1mmake codex_spread_dry_run /Users/username/example\033[0m\n'
	@printf '  \033[32mRight:\033[0m \033[1mmake codex_spread_dry_run SPREAD_DIRS="/Users/username/example"\033[0m\n'

test:
	$(PYTHON) -m unittest $(TEST_ARGS)

check-spread-dirs:
	@test -n "$(strip $(SPREAD_DIRS))" || (echo "Set SPREAD_DIRS='dir1 dir2'. See: make info" >&2; exit 1)

codex_spread_dry_run: check-spread-dirs
	$(PYTHON) $(SPREAD_SCRIPT) $(SPREAD_DIRS)

codex_spread: check-spread-dirs
	$(PYTHON) $(SPREAD_SCRIPT) --apply $(SPREAD_DIRS)
