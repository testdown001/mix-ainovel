import sys

file_path = r'\\wsl.localhost\Ubuntu\home\aikev\code\arboris-novel\backend\app\api\routers\writer.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False

for i, line in enumerate(lines):
    if 'async def _do_post_process():' in line and 185 < i < 195:
        skip = True
    if skip and 'await asyncio.gather(_do_finalize(), _do_post_process())' in line:
        new_lines.append(line.replace('_do_finalize(), _do_post_process()', '_do_finalize()'))
        skip = False
        continue
    
    if 'asyncio.create_task(' in line and 590 < i < 605:
        skip = True
    if skip and 'mode="select",' in line and 600 < i < 610:
        continue
    if skip and '    )' in line and 602 < i < 610:
        skip = False
        continue
        
    if skip:
        continue
        
    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
