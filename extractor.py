import os
import re
import json
import asyncio
import datetime
import http.server
import threading
import subprocess
from telethon import TelegramClient, events

# Configuration file path
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Erro: Arquivo {CONFIG_FILE} não encontrado!")
        print("Por favor, crie o arquivo de configuração baseado no modelo.")
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_message(text):
    if not text:
        return None

    # Clean markdown characters (bold asterisks and code backticks)
    clean_text = text.replace("*", "").replace("`", "")

    # Split into main part and lists part to avoid key collision
    list_headers = [
        "• POSSÍVEIS PARENTES:", "• POSSÍVEIS VIZINHOS:", "• PARTICIPAÇÃO SOCIETÁRIA:", "• VÍNCULOS EMPREGATÍCIOS:",
        "POSSÍVEIS PARENTES:", "POSSÍVEIS VIZINHOS:", "PARTICIPAÇÃO SOCIETÁRIA:", "VÍNCULOS EMPREGATÍCIOS:",
        "POSSIVEIS PARENTES:", "POSSIVEIS VIZINHOS:", "PARTICIPACAO SOCIETARIA:", "VINCULOS EMPREGATICIOS:"
    ]
    
    main_part = clean_text
    lists_part = ""
    
    for header in list_headers:
        if header in clean_text:
            parts = clean_text.split(header, 1)
            main_part = parts[0]
            lists_part = header + parts[1]
            break

    data = {
        "cpf": "", "pis": "", "titulo_eleitoral": "", "rg": "", 
        "data_de_expedicao": "", "orgao_expedidor": "", "uf_rg": "",
        "nome": "", "nascimento": "", "idade": "", "signo": "",
        "mae": "", "pai": "", "nacionalidade": "", "escolaridade": "",
        "estado_civil": "", "profissao": "", "renda_presumida": "",
        "status_receita_federal": "", "score": None, "faixa_de_risco": "",
        "emails": [], "enderecos": [], "telefones_proprietario": [],
        "telefones_comerciais": [], "telefones_referenciais": [],
        "possiveis_parentes": [], "possiveis_vizinhos": [],
        "participacao_societaria": [], "vinculos_empregaticios": []
    }

    # 1. Parse main part (Personal details and contact info)
    key_map = {
        "CPF": "cpf", "PIS": "pis", "TÍTULO ELEITORAL": "titulo_eleitoral", "TITULO ELEITORAL": "titulo_eleitoral",
        "RG": "rg", "DATA DE EXPEDIÇÃO": "data_de_expedicao", "DATA DE EXPEDICAO": "data_de_expedicao",
        "ORGÃO EXPEDIDOR": "orgao_expedidor", "ORGAO EXPEDIDOR": "orgao_expedidor", "UF - RG": "uf_rg", "UF-RG": "uf_rg",
        "NOME": "nome", "NASCIMENTO": "nascimento", "IDADE": "idade", "SIGNO": "signo",
        "MÃE": "mae", "MAE": "mae", "PAI": "pai", "NACIONALIDADE": "nacionalidade",
        "ESCOLARIDADE": "escolaridade", "ESTADO CIVIL": "estado_civil", "PROFISSÃO": "profissao", "PROFISSAO": "profissao",
        "RENDA PRESUMIDA": "renda_presumida", "STATUS RECEITA FEDERAL": "status_receita_federal",
        "SCORE": "score", "FAIXA DE RISCO": "faixa_de_risco"
    }

    contact_list_keys = {
        "E-MAILS": "emails", "EMAILS": "emails",
        "ENDEREÇOS": "enderecos", "ENDERECOS": "enderecos",
        "TELEFONES PROPRIETÁRIO": "telefones_proprietario", "TELEFONES PROPRIETARIO": "telefones_proprietario",
        "TELEFONES COMERCIAIS": "telefones_comerciais",
        "TELEFONES REFERENCIAIS": "telefones_referenciais"
    }

    main_lines = [line.strip() for line in main_part.splitlines()]
    current_list_key = None

    for line in main_lines:
        if not line:
            continue
        
        clean_line = line
        if clean_line.startswith("•") or clean_line.startswith("-") or clean_line.startswith("*"):
            clean_line = clean_line[1:].strip()
            
        if ":" in clean_line:
            parts = clean_line.split(":", 1)
            potential_key = parts[0].strip().upper()
            potential_val = parts[1].strip()
            
            if potential_key in key_map:
                current_list_key = None
                dict_key = key_map[potential_key]
                if dict_key == "score":
                    if data[dict_key] is None:
                        try:
                            data[dict_key] = int(potential_val)
                        except ValueError:
                            data[dict_key] = None
                else:
                    if not data[dict_key]:
                        data[dict_key] = potential_val
                continue
                
            elif potential_key in contact_list_keys:
                current_list_key = contact_list_keys[potential_key]
                if potential_val and potential_val.upper() != "SEM INFORMAÇÃO":
                    data[current_list_key].append(potential_val)
                continue

        if current_list_key:
            if "BY: @" in line or "SkynetBlackRobot" in line:
                current_list_key = None
                continue
            if line.strip() and line.strip().upper() != "SEM INFORMAÇÃO":
                data[current_list_key].append(line.strip())

    # 2. Parse lists part (Relative and neighbor lists)
    if lists_part:
        list_lines = [line.strip() for line in lists_part.splitlines()]
        current_list_key = None
        
        relation_list_keys = {
            "POSSÍVEIS PARENTES": "possiveis_parentes", "POSSIVEIS PARENTES": "possiveis_parentes",
            "POSSÍVEIS VIZINHOS": "possiveis_vizinhos", "POSSIVEIS VIZINHOS": "possiveis_vizinhos",
            "PARTICIPAÇÃO SOCIETÁRIA": "participacao_societaria", "PARTICIPACAO SOCIETARIA": "participacao_societaria",
            "VÍNCULOS EMPREGATÍCIOS": "vinculos_empregaticios", "VINCULOS EMPREGATICIOS": "vinculos_empregaticios"
        }
        
        for line in list_lines:
            if not line:
                continue
            
            clean_line = line
            if clean_line.startswith("•") or clean_line.startswith("-") or clean_line.startswith("*"):
                clean_line = clean_line[1:].strip()
                
            # Check if we are entering a new list section
            if ":" in clean_line:
                parts = clean_line.split(":", 1)
                potential_key = parts[0].strip().upper()
                potential_val = parts[1].strip()
                
                if potential_key in relation_list_keys:
                    current_list_key = relation_list_keys[potential_key]
                    if potential_val and potential_val.upper() != "SEM INFORMAÇÃO":
                        data[current_list_key].append(potential_val)
                    continue
            
            # If in list mode, accumulate the lines
            if current_list_key:
                if "BY: @" in line or "SkynetBlackRobot" in line:
                    current_list_key = None
                    continue
                if line.strip() and line.strip().upper() != "SEM INFORMAÇÃO":
                    data[current_list_key].append(line.strip())

    # We only count this as valid if we extracted at least a NOME and CPF
    if not data["cpf"] or not data["nome"] or data["cpf"].upper() == "SEM INFORMAÇÃO":
        return None

    return data

def verify_criteria(data):
    if not data:
        return False
    
    score = data.get("score")
    faixa = data.get("faixa_de_risco")
    
    if score is None or not faixa:
        return False
    
    # Check if SCORE >= 850
    score_ok = score >= 850
    
    # Check if FAIXA DE RISCO is "BAIXISSIMO RISCO" (case-insensitive)
    faixa_clean = faixa.strip().upper()
    faixa_ok = "BAIXISSIMO RISCO" in faixa_clean or "BAIXÍSSIMO RISCO" in faixa_clean
    
    return score_ok and faixa_ok

def save_to_file(data, txt_filename, json_filename):
    # 1. Format the extracted data nicely for TXT (only the 5 requested fields)
    formatted_entry = (
        "==================================================\n"
        f"NOME: {data['nome']}\n"
        f"CPF: {data['cpf']}\n"
        f"SCORE: {data['score']}\n"
        f"FAIXA DE RISCO: {data['faixa_de_risco']}\n"
        f"RENDA PRESUMIDA: {data['renda_presumida']}\n"
        "==================================================\n\n"
    )
    
    # Append to the TXT file
    with open(txt_filename, "a", encoding="utf-8") as f:
        f.write(formatted_entry)
        
    # 2. Append all fields to the JSON file
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry_dict = {
        **data,
        "timestamp": timestamp
    }
    
    records = []
    if os.path.exists(json_filename):
        try:
            with open(json_filename, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
            
    records.append(entry_dict)
    
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def migrate_txt_to_json(txt_filename, json_filename):
    if os.path.exists(txt_filename) and not os.path.exists(json_filename):
        print("Migrando dados existentes de TXT para JSON...")
        try:
            with open(txt_filename, "r", encoding="utf-8") as f:
                content = f.read()
            
            blocks = content.split("==================================================")
            records = []
            
            # Use fixed dummy date for migrated entries, offset slightly so they sort correctly
            base_time = datetime.datetime.now() - datetime.timedelta(days=1)
            
            for idx, block in enumerate(blocks):
                if not block.strip():
                    continue
                
                nome_match = re.search(r'NOME:\s*([^\n\r]+)', block)
                cpf_match = re.search(r'CPF:\s*([\d.-]+)', block)
                score_match = re.search(r'SCORE:\s*(\d+)', block)
                faixa_match = re.search(r'FAIXA DE RISCO:\s*([^\n\r]+)', block)
                renda_match = re.search(r'RENDA PRESUMIDA:\s*([^\n\r]+)', block)
                
                if cpf_match:
                    entry_time = base_time + datetime.timedelta(seconds=idx)
                    records.append({
                        "nome": nome_match.group(1).strip() if nome_match else "Desconhecido",
                        "cpf": cpf_match.group(1).strip(),
                        "score": int(score_match.group(1).strip()) if score_match else 0,
                        "faixa_de_risco": faixa_match.group(1).strip() if faixa_match else "Desconhecido",
                        "renda_presumida": renda_match.group(1).strip() if renda_match else "SEM INFORMAÇÃO",
                        "timestamp": entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "pis": "SEM INFORMAÇÃO", "titulo_eleitoral": "SEM INFORMAÇÃO", "rg": "SEM INFORMAÇÃO", 
                        "data_de_expedicao": "SEM INFORMAÇÃO", "orgao_expedidor": "SEM INFORMAÇÃO", "uf_rg": "SEM INFORMAÇÃO",
                        "nascimento": "SEM INFORMAÇÃO", "idade": "", "signo": "SEM INFORMAÇÃO",
                        "mae": "SEM INFORMAÇÃO", "pai": "SEM INFORMAÇÃO", "nacionalidade": "SEM INFORMAÇÃO", 
                        "escolaridade": "SEM INFORMAÇÃO", "estado_civil": "SEM INFORMAÇÃO", "profissao": "SEM INFORMAÇÃO",
                        "status_receita_federal": "SEM INFORMAÇÃO", "emails": [], "enderecos": [], 
                        "telefones_proprietario": [], "telefones_comerciais": [], "telefones_referenciais": [],
                        "possiveis_parentes": [], "possiveis_vizinhos": [], "participacao_societaria": [], "vinculos_empregaticios": []
                    })
            
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            print(f"Migração concluída! {len(records)} registros importados no Dashboard.")
        except Exception as e:
            print(f"Aviso: Não foi possível realizar a migração automática para o Dashboard: {e}")

def load_existing_cpfs(json_filename):
    cpfs = set()
    if os.path.exists(json_filename):
        try:
            with open(json_filename, "r", encoding="utf-8") as f:
                records = json.load(f)
                for r in records:
                    if "cpf" in r:
                        cpfs.add(r["cpf"].strip())
        except Exception:
            pass
    return cpfs

# Background Web Server
class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to suppress console spam
        pass

    def do_GET(self):
        # API endpoint serving json data
        if self.path == '/api/data' or self.path == '/extracted_data.json':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            
            json_file = "extracted_data.json"
            if os.path.exists(json_file):
                with open(json_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"[]")
        
        # Route to serve the dashboard HTML
        elif self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html_file = "index.html"
            if os.path.exists(html_file):
                with open(html_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"Dashboard HTML file index.html not found!")
        else:
            # Fallback for icons, styles, etc.
            super().do_GET()

def start_web_server(port=5000):
    handler = DashboardHandler
    server = http.server.ThreadingHTTPServer(('0.0.0.0', port), handler)
    print(f"\n==================================================")
    print(f"   PAINEL WEB LOCAL INICIADO COM SUCESSO!")
    print(f"   Acesse no navegador: http://localhost:{port}")
    print(f"==================================================\n")
    
    # Run server on background daemon thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

def git_push_updates(auto_push_enabled):
    if not auto_push_enabled:
        return
    try:
        # Check if git is initialized
        if not os.path.exists(".git"):
            return
            
        git_path = r"C:\Program Files\Git\cmd\git.exe"
        # Check status
        status = subprocess.run([git_path, "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            return
            
        print("[Git] Novas atualizações detectadas! Enviando para o GitHub...")
        subprocess.run([git_path, "add", "extracted_data.json", "extracted_data.txt"], check=True)
        subprocess.run([git_path, "commit", "-m", "auto: update data"], check=True)
        subprocess.run([git_path, "push"], check=True)
        print("[Git] Upload concluído com sucesso no GitHub Pages!")
    except Exception as e:
        print(f"[Git] Erro ao enviar para o GitHub: {e}")

async def main():
    config = load_config()
    if not config:
        return

    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    phone = config.get("phone")
    groups = config.get("groups", [])
    output_file_txt = config.get("output_file", "extracted_data.txt")
    output_file_json = output_file_txt.replace(".txt", ".json")
    auto_git_push = config.get("auto_git_push", False)

    if api_id == 1234567 or api_hash == "YOUR_API_HASH_HERE":
        print("Erro: Por favor, configure seu api_id e api_hash no arquivo config.json!")
        return

    # Load already extracted CPFs to prevent duplication
    existing_cpfs = load_existing_cpfs(output_file_json)
    print(f"Carregados {len(existing_cpfs)} CPFs existentes do banco de dados.")

    # Start built-in Web Dashboard Server
    start_web_server(port=5000)

    print("Iniciando o cliente do Telegram...")
    client = TelegramClient("extractor_session", api_id, api_hash)
    await client.start(phone=phone)
    print("Autenticado com sucesso!")
    print("Iniciando varredura completa. Todos os campos adicionais serão extraídos do histórico.")

    async def process_telegram_message(message_text, message_id, chat_title):
        data = parse_message(message_text)
        if data and verify_criteria(data):
            cpf = data["cpf"]
            if cpf not in existing_cpfs:
                existing_cpfs.add(cpf)
                save_to_file(data, output_file_txt, output_file_json)
                print(f"[+] Extraído e salvo completo: NOME={data['nome']}, CPF={cpf}, SCORE={data['score']} (Grupo: {chat_title})")
            else:
                pass  # Keep logs clean

    # 1. Scrape History from configured groups
    print("\n--- LENDO HISTÓRICO DOS GRUPOS ---")
    for group in groups:
        try:
            print(f"Lendo histórico do grupo: {group}...")
            entity = await client.get_entity(group)
            chat_title = getattr(entity, 'title', str(group))
            
            # Scrape all messages in history
            count = 0
            async for message in client.iter_messages(entity, limit=None):
                count += 1
                if count % 100 == 0:
                    print(f"[{chat_title}] Histórico: Lidas {count} mensagens...")
                if message.text:
                    await process_telegram_message(message.text, message.id, chat_title)
            print(f"Leitura de histórico concluída para {chat_title}. Total de {count} mensagens processadas.")
            
            # Trigger push after history is loaded
            git_push_updates(auto_git_push)
        except Exception as e:
            print(f"Erro ao ler histórico do grupo {group}: {e}")

    # 2. Setup auto Git push loop for real-time updates
    async def git_push_loop():
        if not auto_git_push:
            return
        while True:
            await asyncio.sleep(180) # Check every 3 minutes
            git_push_updates(auto_git_push)

    # Start the push task in the background
    asyncio.create_task(git_push_loop())

    # 3. Setup Real-time Listener
    print("\n--- MONITORANDO EM TEMPO REAL ---")
    print("Aguardando novas mensagens... Pressione Ctrl+C para parar.")

    # Convert groups list to entities for the event handler
    group_entities = []
    for group in groups:
        try:
            entity = await client.get_entity(group)
            group_entities.append(entity)
        except Exception as e:
            print(f"Não foi possível registrar o grupo {group} para escuta em tempo real: {e}")

    if not group_entities:
        print("Aviso: Nenhum grupo pôde ser registrado para monitoramento em tempo real. Verifique os nomes dos grupos.")
        return

    @client.on(events.NewMessage(chats=group_entities))
    async def handler(event):
        if event.message and event.message.text:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Grupo Desconhecido')
            await process_telegram_message(event.message.text, event.message.id, chat_title)

    # Keep running
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrograma encerrado pelo usuário.")
