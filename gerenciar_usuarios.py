"""
Gerenciador de Usuários — Dashboard de Engenharia de Cardápio
═════════════════════════════════════════════════════════════
Script interativo para gerenciar usuários no MongoDB Atlas.

Uso:  python gerenciar_usuarios.py
"""

import bcrypt
import sys
from pymongo import MongoClient

# ──────────────────────────────────────────────
# Conexão com o MongoDB Atlas
# ──────────────────────────────────────────────
MONGO_URI = "mongodb+srv://lucasrecksan:120511@cluster0.wnkv81p.mongodb.net/?appName=Cluster0"


def conectar():
    """Conecta ao MongoDB e retorna a coleção de usuários."""
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command("ping")
        db = client["cardapio_auth"]
        return db["usuarios"]
    except Exception as e:
        print(f"\n[ERRO] Falha ao conectar ao MongoDB: {e}")
        sys.exit(1)


def gerar_hash(senha: str) -> str:
    """Gera hash bcrypt a partir de uma senha."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def listar_usuarios(colecao):
    """Lista todos os usuários cadastrados."""
    usuarios = list(colecao.find({}, {"_id": 0, "password_hash": 0}))
    if not usuarios:
        print("\n  Nenhum usuario cadastrado.\n")
        return
    print(f"\n  {'Username':<20} {'Nome':<25} {'Email'}")
    print("  " + "-" * 70)
    for u in usuarios:
        print(f"  {u.get('username', '?'):<20} {u.get('name', '?'):<25} {u.get('email', '?')}")
    print(f"\n  Total: {len(usuarios)} usuario(s)\n")


def criar_usuario(colecao):
    """Cria um novo usuário no banco."""
    print("\n--- Criar Novo Usuario ---\n")

    username = input("  Username (login): ").strip().lower()
    if not username:
        print("  [ERRO] Username nao pode ser vazio.")
        return

    # Verifica se já existe
    if colecao.find_one({"username": username}):
        print(f"  [ERRO] O username '{username}' ja existe no banco.")
        return

    nome = input("  Nome completo: ").strip()
    email = input("  Email: ").strip()
    senha = input("  Senha: ").strip()

    if not senha:
        print("  [ERRO] Senha nao pode ser vazia.")
        return

    documento = {
        "username": username,
        "name": nome if nome else username,
        "email": email,
        "password_hash": gerar_hash(senha),
    }

    colecao.insert_one(documento)
    print(f"\n  [OK] Usuario '{username}' criado com sucesso!")
    print(f"  Login: {username}")
    print(f"  Senha: {senha}\n")


def remover_usuario(colecao):
    """Remove um usuário do banco."""
    print("\n--- Remover Usuario ---\n")
    username = input("  Username para remover: ").strip().lower()

    if not username:
        print("  [ERRO] Username nao pode ser vazio.")
        return

    resultado = colecao.delete_one({"username": username})
    if resultado.deleted_count > 0:
        print(f"  [OK] Usuario '{username}' removido com sucesso!\n")
    else:
        print(f"  [ERRO] Usuario '{username}' nao encontrado.\n")


def alterar_senha(colecao):
    """Altera a senha de um usuário existente."""
    print("\n--- Alterar Senha ---\n")
    username = input("  Username: ").strip().lower()

    if not colecao.find_one({"username": username}):
        print(f"  [ERRO] Usuario '{username}' nao encontrado.")
        return

    nova_senha = input("  Nova senha: ").strip()
    if not nova_senha:
        print("  [ERRO] Senha nao pode ser vazia.")
        return

    colecao.update_one(
        {"username": username},
        {"$set": {"password_hash": gerar_hash(nova_senha)}},
    )
    print(f"\n  [OK] Senha do usuario '{username}' alterada com sucesso!\n")


def menu():
    """Menu principal interativo."""
    print("\n" + "=" * 50)
    print("  GERENCIADOR DE USUARIOS - Eng. de Cardapio")
    print("=" * 50)

    colecao = conectar()
    print("  Conectado ao MongoDB Atlas!\n")

    while True:
        print("  [1] Listar usuarios")
        print("  [2] Criar novo usuario")
        print("  [3] Remover usuario")
        print("  [4] Alterar senha")
        print("  [0] Sair")

        opcao = input("\n  Opcao: ").strip()

        if opcao == "1":
            listar_usuarios(colecao)
        elif opcao == "2":
            criar_usuario(colecao)
        elif opcao == "3":
            remover_usuario(colecao)
        elif opcao == "4":
            alterar_senha(colecao)
        elif opcao == "0":
            print("\n  Ate mais!\n")
            break
        else:
            print("  Opcao invalida.\n")


if __name__ == "__main__":
    menu()
