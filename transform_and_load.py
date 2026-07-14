import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).parent
RAW_JOBS_FILE = BASE_DIR / "raw_jobs.json"

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv(BASE_DIR / ".env")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

# Validação simples pra falhar rápido caso o .env esteja incompleto
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    raise EnvironmentError(
        "Variáveis de ambiente do banco não encontradas. Confira se o arquivo .env existe "
        "e contém DB_USER, DB_PASSWORD, DB_HOST, DB_PORT e DB_NAME."
    )

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Sintaxe adaptada para PostgreSQL ---
# UNIQUE já é implícito em PRIMARY KEY, mas deixei explícito para reforçar a intenção
# de que 'link' é a chave usada para evitar duplicatas.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vagas (
    link TEXT PRIMARY KEY NOT NULL,
    titulo TEXT,
    empresa TEXT,
    localizacao TEXT,
    salario_min REAL,
    salario_max REAL,
    data_extracao TEXT NOT NULL
)
"""

# No SQLite usávamos "INSERT OR IGNORE". No Postgres, o equivalente é
# "ON CONFLICT (coluna) DO NOTHING", que exige que a coluna tenha uma
# UNIQUE constraint ou seja PRIMARY KEY (que já é o nosso caso, com 'link').
INSERT_SQL = """
INSERT INTO vagas (
    link,
    titulo,
    empresa,
    localizacao,
    salario_min,
    salario_max,
    data_extracao
) VALUES (
    :link,
    :titulo,
    :empresa,
    :localizacao,
    :salario_min,
    :salario_max,
    :data_extracao
)
ON CONFLICT (link) DO NOTHING
"""


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = re.sub(r"\s+", " ", str(value).replace("\n", " ").replace("\r", " ")).strip()
    return cleaned or None


def parse_brl_amount(raw_amount: str) -> float:
    normalized = (
        raw_amount.replace("R$", "")
        .replace("\xa0", " ")
        .strip()
        .replace(".", "")
        .replace(",", ".")
    )
    return float(normalized)


def parse_salary(salary: str | None) -> tuple[float | None, float | None]:
    cleaned = clean_text(salary)
    if not cleaned:
        return None, None

    if cleaned.lower() == "a combinar":
        return None, None

    amounts = re.findall(r"R\$\s*[\d.]+\,\d{2}", cleaned, flags=re.IGNORECASE)
    if not amounts:
        return None, None

    values = [parse_brl_amount(amount) for amount in amounts]
    if len(values) == 1:
        return values[0], values[0]

    return float(min(values)), float(max(values))


def load_raw_jobs() -> list[dict]:
    with RAW_JOBS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def transform_jobs(raw_jobs: list[dict]) -> pd.DataFrame:
    extraction_time = datetime.now().isoformat(timespec="seconds")
    transformed_rows: list[dict] = []

    for job in raw_jobs:
        salario_min, salario_max = parse_salary(job.get("salario"))
        link = clean_text(job.get("link"))

        if not link:
            continue

        transformed_rows.append(
            {
                "link": link,
                "titulo": clean_text(job.get("titulo")),
                "empresa": clean_text(job.get("empresa")),
                "localizacao": clean_text(job.get("localizacao")),
                "salario_min": salario_min,
                "salario_max": salario_max,
                "data_extracao": extraction_time,
            }
        )

    return pd.DataFrame(transformed_rows)


def load_to_database(df: pd.DataFrame, engine) -> tuple[int, int]:
    with engine.begin() as connection:
        connection.execute(text(CREATE_TABLE_SQL))

        before_count = connection.execute(text("SELECT COUNT(*) FROM vagas")).scalar_one()
        records = df.to_dict(orient="records")

        if records:
            connection.execute(text(INSERT_SQL), records)

        after_count = connection.execute(text("SELECT COUNT(*) FROM vagas")).scalar_one()

    inserted = after_count - before_count
    ignored = len(records) - inserted
    return inserted, ignored


def main() -> None:
    if not RAW_JOBS_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {RAW_JOBS_FILE}")

    raw_jobs = load_raw_jobs()
    df = transform_jobs(raw_jobs)

    if df.empty:
        print("Nenhuma vaga válida encontrada em raw_jobs.json.")
        return

    engine = create_engine(DATABASE_URL)
    inserted, ignored = load_to_database(df, engine)

    print(f"Processadas {len(df)} vagas do arquivo JSON.")
    print(f"Inseridas: {inserted} | Ignoradas (duplicadas): {ignored}")
    print(f"Banco de dados: {DB_HOST}/{DB_NAME}")


if __name__ == "__main__":
    main()