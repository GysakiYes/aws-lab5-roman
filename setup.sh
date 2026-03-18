#!/bin/bash
set -e

REPO_URL="$1"
PROJECT_DIR="aws-lab5-cloned"

if [ -z "$REPO_URL" ]; then
  echo "Використання: ./setup.sh <git_repo_url>"
  exit 1
fi

sudo apt update
sudo apt install -y git python3 python3-pip python3-venv

rm -rf "$PROJECT_DIR"
git clone "$REPO_URL" "$PROJECT_DIR"

cd "$PROJECT_DIR"

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "Готово."
echo "Репозиторій клоновано."
echo "Віртуальне середовище створено."
echo "Залежності встановлено."
