import os
import sys

def compile_proto():
    print("Compilando arquivos proto...")
    proto_file = "chat.proto"
    
    if not os.path.exists(proto_file):
        print(f"Erro: arquivo {proto_file} não encontrado!")
        sys.exit(1)
        
    os.system(f"python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. {proto_file}")
    print("Compilação concluída!")

if __name__ == "__main__":
    compile_proto()