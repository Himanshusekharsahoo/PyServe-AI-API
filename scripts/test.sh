#!/usr/bin/env bash

set -xe

pytest -vv --cov=app --cov=tests --cov-report=term-missing --cov-report=xml tests/ ${@}
