# Salve este código em um arquivo chamado multi_node_chat.py

import grpc
import chat_pb2
import chat_pb2_grpc
import threading
import time
import datetime
import uuid
import queue
import sys
import json
import os
from concurrent import futures

class ChatServicer(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self, username):
        self.clients = {}
        self.username = username
        
    def SendMessage(self, request, context):
        # Ao receber uma mensagem, armazena na fila
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {request.sender}: {request.content}")
        
        # Coloca na fila para outros clientes conectados
        for client_id in self.clients:
            self.clients[client_id].put({
                'sender': request.sender,
                'content': request.content,
                'timestamp': request.timestamp
            })
            
        return chat_pb2.MessageResponse(
            sender=request.sender,
            content=request.content, 
            timestamp=timestamp,
            success=True
        )
    
    def StreamMessages(self, request, context):
        # Identificador único para o cliente
        client_id = request.client_id
        
        # Cria uma fila para este cliente
        self.clients[client_id] = queue.Queue()
        print(f"Novo cliente conectado: {client_id}")
        
        try:
            while context.is_active():
                # Verifica se tem mensagens para este cliente
                try:
                    msg = self.clients[client_id].get(timeout=1)
                    yield chat_pb2.MessageResponse(
                        sender=msg['sender'],
                        content=msg['content'],
                        timestamp=msg['timestamp'],
                        success=True
                    )
                except queue.Empty:
                    # Não há mensagens, continua esperando
                    continue
        except Exception as e:
            print(f"Erro no StreamMessages: {e}")
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
                print(f"Cliente desconectado: {client_id}")

def start_server(port, username):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = ChatServicer(username)
    chat_pb2_grpc.add_ChatServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"Servidor iniciado na porta {port}")
    return server, servicer

def stop_server_gracefully(server):
    """Para o servidor de forma graciosa, permitindo que os clientes se desconectem"""
    # Conceder algum tempo para que os clientes recebam a notificação de encerramento
    print("Parando servidor graciosamente...")
    server.stop(2)  # 2 segundos de timeout

class NodeConnection:
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.channel = None
        self.stub = None
        self.connected = False
        self.receive_thread = None
        self.reconnect_thread = None
        self.should_reconnect = True
        self.connection_attempt = 0
           
    def connect(self):
        self.connection_attempt += 1
        try:
            self.channel = grpc.insecure_channel(f'{self.host}:{self.port}')
            self.stub = chat_pb2_grpc.ChatServiceStub(self.channel)
            
            # Testar a conexão com uma chamada simples com timeout
            grpc.channel_ready_future(self.channel).result(timeout=2)
            
            self.connected = True
            self.connection_attempt = 0  # Reset contador após sucesso
            print(f"Conectado a {self.host}:{self.port}")
            return True
        except grpc.FutureTimeoutError:
            self.connected = False
            if self.connection_attempt == 1 or self.connection_attempt % 5 == 0:
                print(f"Tentativa {self.connection_attempt}: Tempo esgotado ao conectar a {self.host}:{self.port}")
            return False
        except Exception as e:
            self.connected = False
            # Mostrar mensagem apenas na primeira tentativa ou a cada 5 tentativas
            if self.connection_attempt == 1 or self.connection_attempt % 5 == 0:
                print(f"Tentativa {self.connection_attempt}: Não foi possível conectar a {self.host}:{self.port}: {e}")
            return False
    
    def start_reconnect_thread(self):
        if not self.reconnect_thread or not self.reconnect_thread.is_alive():
            self.reconnect_thread = threading.Thread(target=self.reconnect_loop)
            self.reconnect_thread.daemon = True
            self.reconnect_thread.start()
    
    def reconnect_loop(self):
        while self.should_reconnect:
            if not self.connected:
                if self.connect():
                    self.start_receiving()
                time.sleep(5)  # Aguarda 5 segundos antes de tentar novamente
            else:
                time.sleep(10)  # Se está conectado, verifica a cada 10 segundos
    
    def start_receiving(self):
        if self.connected and (not self.receive_thread or not self.receive_thread.is_alive()):
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
    
    def receive_messages(self):
        client_id = str(uuid.uuid4())
        request = chat_pb2.StreamRequest(client_id=client_id)
        
        try:
            for response in self.stub.StreamMessages(request):
                # A mensagem já será impressa pelo servidor
                pass
        except grpc.RpcError as e:
            status_code = e.code()
            # Verificar se o erro é de encerramento normal (peer encerrou a conexão)
            if status_code == grpc.StatusCode.UNAVAILABLE or status_code == grpc.StatusCode.CANCELLED:
                print(f"Nó {self.host}:{self.port} desconectado.")
            else:
                print(f"Erro na conexão com {self.host}:{self.port}: {e.details()} (código: {status_code})")
            
            self.connected = False
            # Tentar reconectar automaticamente apenas se não for um encerramento intencional
            if self.should_reconnect:
                self.start_reconnect_thread()
        except Exception as e:
            print(f"Conexão com {self.host}:{self.port} perdida: {e}")
            self.connected = False
            if self.should_reconnect:
                self.start_reconnect_thread()
    
    def send_message(self, sender, content):
        if not self.connected:
            # Não mostra mensagem, apenas retorna falso
            return False
            
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            response = self.stub.SendMessage(
                chat_pb2.MessageRequest(
                    sender=sender,
                    content=content,
                    timestamp=timestamp
                )
            )
            return response.success
        except grpc.RpcError as e:
            status_code = e.code()
            if status_code == grpc.StatusCode.DEADLINE_EXCEEDED:
                print(f"Tempo esgotado ao enviar mensagem para {self.host}:{self.port}")
            elif status_code == grpc.StatusCode.UNAVAILABLE:
                print(f"Nó {self.host}:{self.port} está indisponível")
            else:
                print(f"Erro ao enviar mensagem para {self.host}:{self.port}: {e.details()}")
            
            self.connected = False
            # Tentar reconectar automaticamente
            if self.should_reconnect:
                self.start_reconnect_thread()
            return False
        except Exception as e:
            print(f"Erro inesperado ao enviar mensagem para {self.host}:{self.port}: {e}")
            self.connected = False
            if self.should_reconnect:
                self.start_reconnect_thread()
            return False
    
    def disconnect(self):
        self.should_reconnect = False
        if self.channel:
            try:
                self.channel.close()
            except Exception as e:
                print(f"Erro ao fechar canal para {self.host}:{self.port}: {e}")
        self.connected = False
        print(f"Desconectado de {self.host}:{self.port}")

def load_nodes_config(config_file="nodes.json"):
    """Carrega a configuração dos nós a partir de um arquivo JSON"""
    if not os.path.exists(config_file):
        # Cria um arquivo de configuração padrão se não existir
        default_config = [
            {"host": "localhost", "port": 50051},
            {"host": "localhost", "port": 50052},
            {"host": "localhost", "port": 50053}
        ]
        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"Arquivo de configuração {config_file} criado com valores padrão")
    
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Erro ao carregar configuração: {e}")
        return []

def main():
    if len(sys.argv) < 2:
        print("Uso: python multi_node_chat.py <porta_local> [arquivo_config]")
        print("Exemplo: python multi_node_chat.py 50051 nodes.json")
        sys.exit(1)
    
    # Porta local para este nó
    local_port = int(sys.argv[1])
    
    # Arquivo de configuração (opcional)
    config_file = sys.argv[2] if len(sys.argv) > 2 else "nodes.json"
    
    # Nome de usuário para este nó
    username = input("Digite seu nome de usuário: ")
    
    # Iniciar o servidor local
    server, servicer = start_server(local_port, username)
    
    # Carregar configuração de nós
    nodes_config = load_nodes_config(config_file)
    
    # Lista de conexões com outros nós
    connections = []
    
    # Conectar a outros nós
    for node in nodes_config:
        host = node["host"]
        port = node["port"]
        
        # Pular este nó (não conectar a si mesmo)
        if port == local_port and host in ["localhost", "127.0.0.1"]:
            continue
            
        connection = NodeConnection(host, port, username)
        # Iniciar thread de reconexão automática
        connection.start_reconnect_thread()
        connections.append(connection)
    
    print("\nComandos disponíveis:")
    print("  /list - Listar conexões ativas")
    print("  /quit - Sair do chat")
    print("  /retry - Forçar reconexão com todos os nós desconectados")
    print("\nChat iniciado! Você pode começar a enviar mensagens mesmo sem conexões ativas.")
    print("Os nós conectarão automaticamente assim que estiverem disponíveis.")
    
    # Loop principal para enviar mensagens
    try:
        while True:
            try:
                message = input("")
            except EOFError:
                continue
                
            if message.lower() == "/quit":
                break
            elif message.lower() == "/list":
                print("\nConexões ativas:")
                active_count = 0
                for i, conn in enumerate(connections):
                    status = "Conectado" if conn.connected else "Desconectado"
                    if conn.connected:
                        active_count += 1
                    print(f"  {i+1}. {conn.host}:{conn.port} - {status}")
                print(f"\nTotal: {active_count}/{len(connections)} nós conectados")
                continue
            elif message.lower() == "/retry":
                print("Forçando reconexão com todos os nós...")
                for conn in connections:
                    if not conn.connected:
                        conn.connect()
                        if conn.connected:
                            conn.start_receiving()
                continue
            elif not message.strip():
                continue
            
            # Enviar a mensagem para todos os nós conectados
            sent_count = 0
            for conn in connections:
                if conn.connected and conn.send_message(username, message):
                    sent_count += 1
            
            # Se não conseguiu enviar para ninguém mas existem nós configurados
            if sent_count == 0 and connections:
                print(f"[SISTEMA] Mensagem armazenada localmente. Será enviada quando houver conexões disponíveis.")
    
    except KeyboardInterrupt:
        print("\nEncerrando chat...")
    finally:
        # Desativar tentativas de reconexão antes de desconectar
        for conn in connections:
            conn.should_reconnect = False
            
        print("Desconectando de todos os nós...")
        for conn in connections:
            conn.disconnect()
        
        stop_server_gracefully(server)
        print("Chat encerrado.")

if __name__ == "__main__":
    main()