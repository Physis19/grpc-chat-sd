# Chat Distribuído com gRPC

Este projeto implementa um chat distribuído usando gRPC, onde os participantes (nós) podem enviar e receber mensagens simultaneamente, sem a necessidade de esperar uma resposta antes de enviar outra mensagem. O sistema suporta comunicação concorrente entre múltiplos nós.

## Tecnologias Utilizadas
- **Python**
- **gRPC** (Google Remote Procedure Call)
- **Protocol Buffers**
- **Threads e Concorrência**

## Estrutura do Projeto
- `chat.proto` - Define a interface do serviço gRPC
- `compile_proto.py` - Script para compilar o arquivo proto
- `chat_node.py` - Implementação do chat distribuído
- `nodes.json` - Arquivo de configuração com os nós do chat

## Configuração e Execução
### 1. Instalação das Dependências
Certifique-se de ter o Python instalado e instale as dependências necessárias:
```sh
pip install grpcio grpcio-tools
```

### 2. Compilar o Arquivo `.proto`
Antes de rodar o chat, compile o arquivo proto para gerar as classes necessárias:
```sh
python compile_proto.py
```

### 3. Configuração dos Nós
O arquivo `nodes.json` é utilizado para configurar os nós com os quais o chat irá se conectar. Um exemplo de configuração:
```json
[
  {"host": "localhost", "port": 50051},
  {"host": "localhost", "port": 50052},
  {"host": "localhost", "port": 50053}
]
```
Caso o arquivo `nodes.json` não exista, ele será criado automaticamente com valores padrão.

### 4. Iniciar os Nós do Chat
Cada nó deve ser iniciado em uma porta diferente. Para rodar um nó localmente, use:
```sh
python chat_node.py <PORTA>
```
Exemplo:
```sh
python chat_node.py 50051
```
Se houver um arquivo `nodes.json`, ele será usado para configurar a conexão entre os nós automaticamente.

### 5. Comandos Disponíveis no Chat
Durante a execução do chat, os seguintes comandos podem ser usados:
- `/list` - Lista os nós conectados
- `/quit` - Sai do chat
- `/retry` - Força a reconexão com os nós

## Estrutura das Classes

### `ChatServicer`
Esta classe implementa o serviço gRPC definido no `chat.proto`. Suas principais responsabilidades incluem:
- Armazenar os clientes conectados e suas filas de mensagens.
- Receber mensagens enviadas por um cliente e propagá-las para os demais.
- Criar e gerenciar a fila de mensagens para cada cliente conectado.
- Remover clientes quando se desconectam.

### `NodeConnection`
Responsável por gerenciar a conexão de um nó com outros nós. Suas funcionalidades incluem:
- Estabelecer e manter a conexão com outros nós da rede.
- Implementar um mecanismo de reconexão automática caso a conexão seja perdida.
- Criar uma thread dedicada para receber mensagens continuamente.
- Enviar mensagens para outros nós conectados.
- Fechar a conexão de forma segura ao sair do chat.

### `main()`
A função principal do programa que:
- Inicia um servidor gRPC em uma porta especificada.
- Carrega a configuração dos nós a partir do `nodes.json`.
- Estabelece conexões com outros nós e inicia o processo de troca de mensagens.
- Gerencia a interface de linha de comando, permitindo comandos como listar nós, forçar reconexões e sair do chat.



