import os
import http.server
import subprocess
import tempfile
import json
import debugpy
from multiprocessing import Process

hostName = "localhost"
serverPort = 8080
debugPort = 5678
temp_dir = None
vs_token = '12345678'
vs_host = '127.0.0.1'
vs_port = '8000'
vs_proc = None

debug_proc = None

def write_text_file(filepath: str, content: str):
    f = open(filepath, "w")
    f.write(content)
    f.close()

def start_vsweb():
    global vs_proc
    print('start vscode web server')
    vs_proc = subprocess.Popen(['code', 'serve-web', '--without-connection-token', '--accept-server-license-terms', f'--host={vs_host}', f'--port={vs_port}'], shell=True)
    return

def make_url(target_dir: str):
    return f'http://{vs_host}:{vs_port}/?folder=/{target_dir}'

def init_debug(code: str):
    dirname = tempfile.mkdtemp(dir=temp_dir)
    print('created temporary directory', dirname)
    main_py = os.path.join(dirname, "main.py")

    write_text_file(main_py, code)
    os.makedirs(os.path.join(dirname, ".vscode"), exist_ok=True)
    write_text_file(os.path.join(dirname, ".vscode", "launch.json"), json.dumps({
        "configurations": [{
            "name": "Python Debugger: Remote Attach",
            "type": "debugpy",
            "request":"attach",
            "connect":{"host":"localhost","port": debugPort},
            "pathMappings":[
                {"localRoot":"${workspaceFolder}/main.py", "remoteRoot": main_py},
            ],
            "justMyCode": False
        }],
        "version":"0.2.0"
    }))

    return dirname

def start_debug(invisible_code: str, debug_code: str, target_dir: str):
    _globals = dict()
    _locals = dict()

    print("Run invisible code")
    exec(invisible_code, _globals, _locals)

    main_py = os.path.join(target_dir, "main.py")
    compiled_code = compile(debug_code, main_py, "exec")
    debugpy.listen(debugPort)

    # proc = subprocess.Popen(['code', dirname, main_py], shell=True)

    print("Waiting for debugger attach")
    debugpy.wait_for_client()
    exec(compiled_code, _globals, _locals)


class MyServer(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        global debug_proc

        if not (debug_proc is None):
            debug_proc.join()

        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()

        content_len = int(self.headers.get('Content-Length'))

        content = self.rfile.read(content_len)

        data = json.loads(content)

        invisible_code = data['invisible']
        debug_code = data['debug']

        target_dir = init_debug(debug_code)

        debug_proc = Process(target=start_debug, args=(invisible_code, debug_code, target_dir))
        debug_proc.start()

        print('target_dir =', target_dir)

        url = make_url(target_dir)
        print('url =', url)

        self.wfile.write(bytes(url, "utf8"))

if __name__ == "__main__":
    os.makedirs("temp", exist_ok=True)
    temp_dir = os.path.abspath("./temp")

    web_dir = os.path.join(os.path.dirname(__file__), 'frontend')
    os.chdir(web_dir)

    start_vsweb()

    webServer = http.server.ThreadingHTTPServer((hostName, serverPort), MyServer)
    print("Server started http://%s:%s" % (hostName, serverPort))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    if not(vs_proc is None):
        vs_proc.kill()

    webServer.server_close()
    print("Server stopped.")