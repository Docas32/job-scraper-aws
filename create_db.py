from sqlalchemy import create_engine, text

DB_USER = "docas32"
DB_PASSWORD = "sf=wjDQo3$"
DB_HOST = "jobs-db.cj4wkyooc6m7.sa-east-1.rds.amazonaws.com"
DB_PORT = "5432"

# Conecta no banco padrão "postgres" (que sempre existe) para poder criar o novo banco
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"

def main():
    # isolation_level="AUTOCOMMIT" é obrigatório aqui:
    # CREATE DATABASE não pode rodar dentro de uma transação normal
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")

    with engine.connect() as connection:
        connection.execute(text("CREATE DATABASE jobs_db;"))
        print("Banco 'jobs_db' criado com sucesso!")

if __name__ == "__main__":
    main()