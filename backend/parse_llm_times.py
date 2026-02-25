import re
from datetime import datetime

log_file = '/home/aikev/code/arboris-novel/backend/logs/llm.log'

req_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \[INFO\].*?\[\{.*?\'content_length\': (\d+)\}\]')
resp_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \[INFO\].*?LLM响应.*?(?:len=(\d+)|chars=(\d+))')
success_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \[INFO\].*?LLM response success.*?(?:len=(\d+)|chars=(\d+))')

reqs = []
resps = []

with open(log_file, 'r', encoding='utf-8') as f:
    for line in f:
        if "LLM请求(" in line:
            m = req_pattern.search(line)
            if m:
                ts, size = m.groups()
                reqs.append({'ts': datetime.strptime(ts, '%Y-%m-%d %H:%M:%S,%f'), 'size': int(size)})
        elif "LLM response success" in line:
            m = success_pattern.search(line)
            if m:
                ts, l1, l2 = m.groups()
                sz = int(l1) if l1 else int(l2) if l2 else 0
                resps.append({'ts': datetime.strptime(ts, '%Y-%m-%d %H:%M:%S,%f'), 'size': sz})

last_resp_idx = 0
for req in reqs:
    found = False
    for i in range(last_resp_idx, len(resps)):
        resp = resps[i]
        if resp['ts'] > req['ts']:
            duration = (resp['ts'] - req['ts']).total_seconds()
            print(f"Req Size: {req['size']:5} | Resp Size: {resp['size']:5} | Time: {duration:6.2f}s | Stage: ", end="")
            if req['size'] < 2000:
                print("Context/Blueprint")
            elif 2000 < req['size'] < 8000:
                if resp['size'] < 1000:
                    print("Review/Critique/Consistency")
                else:
                    print("Generation (Draft) / Polish")
            elif req['size'] > 10000:
                print("Generation (Full chapter)")
            else:
                print("Unknown")
            last_resp_idx = i + 1
            found = True
            break
    if not found:
        print(f"Req Size: {req['size']} | Timeout/Pending")

