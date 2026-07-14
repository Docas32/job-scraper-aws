from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# --- Dados de conexão ---
DB_USER = "docas32"
DB_PASSWORD = "sf=wjDQo3$"
DB_HOST = "jobs-db.cj4wkyooc6m7.sa-east-1.rds.amazonaws.com"
DB_PORT = "5432"
DB_NAME = "jobs_db"

# Monta a URL de conexão no formato que o SQLAlchemy espera
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def main():
    try:
        # echo=True mostra as queries SQL executadas no terminal (bom para debug)
        engine = create_engine(DATABASE_URL, echo=False)

        with engine.connect() as connection:
            print("Conexão com a AWS bem sucedida!")

            # Cria uma tabela de teste só para provar que a conexão tem permissão de escrita
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS test_connection (
                    id SERIAL PRIMARY KEY,
                    mensagem VARCHAR(100),
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # Insere uma linha de teste
            connection.execute(text("""
                INSERT INTO test_connection (mensagem) VALUES ('Teste de conexão OK');
            """))

            # Confirma a transação (necessário no SQLAlchemy 2.x)
            connection.commit()

            # Lê de volta para confirmar que gravou
            result = connection.execute(text("SELECT id, mensagem, criado_em FROM test_connection;"))
            print("\nConteúdo da tabela 'test_connection':")
            for row in result:
                print(row)

    except OperationalError as e:
        print("Falha ao conectar no banco. Verifique:")
        print("- Se o Security Group libera seu IP atual na porta 5432")
        print("- Se usuário/senha/endpoint estão corretos")
        print(f"\nErro original: {e}")

if __name__ == "__main__":
    main()