#! /usr/bin/env bash

set -xe

isort .

mypy app tests scripts

black --check app tests scripts

flake8 app tests scripts

bandit -r app/
