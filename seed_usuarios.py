"""
Script para popular o MongoDB Atlas com os usuários de teste.
═════════════════════════════════════════════════════════════
Execute UMA VEZ para criar os dois usuários no banco:
    python seed_usuarios.py

Os hashes bcrypt são gerados automaticamente.
"""

import bcrypt
from pymongo import MongoClient

# ──────────────────────────────────────────────
# CONFIGURAÇÃO — Substitua pela sua URI do Atlas
# ──────────────────────────────────────────────
MONGO_URI = "mongodb+srv://lucasrecksan:120511@cluster0.wnkv81p.mongodb.net/?appName=Cluster0"

# ──────────────────────────────────────────────
# Função para gerar hash bcrypt
# ──────────────────────────────────────────────
def gerar_hash(senha: str) -> str:
    """Gera hash bcrypt a partir de uma senha em texto puro."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ──────────────────────────────────────────────
# Usuários de teste
# ──────────────────────────────────────────────
USUARIOS = [
    {
        "username": "admin",
        "name": "Administrador",
        "email": "admin@cardapio.com",
        "password_hash": gerar_hash("Admin$Cardapio2024!"),
    },
    {
        "username": "cliente1",
        "name": "Cliente Restaurante",
        "email": "cliente1@cardapio.com",
        "password_hash": gerar_hash("123456"),
    },
]


def main():
    print("🔌 Conectando ao MongoDB Atlas...")
    client = MongoClient(MONGO_URI)

    # Testa a conexão
    client.admin.command("ping")
    print("✅ Conexão bem-sucedida!")

    db = client["cardapio_auth"]
    colecao = db["usuarios"]

    # Limpa coleção existente (opcional — para recriação limpa)
    colecao.delete_many({})
    print("🗑️  Coleção 'usuarios' limpa.")

    # Insere os usuários
    resultado = colecao.insert_many(USUARIOS)
    print(f"✅ {len(resultado.inserted_ids)} usuários inseridos com sucesso!")

    print("   👤 admin / senha: Admin$Cardapio2024!")
    print("   👤 cliente1 / senha: 123456")

    print("\n🎉 Pronto! Agora você pode rodar: streamlit run app.py")


if __name__ == "__main__":
    main()
