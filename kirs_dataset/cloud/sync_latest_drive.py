import json,subprocess,sys
from pathlib import Path
import yaml

root=Path(__file__).resolve().parents[1]
c=yaml.safe_load((root/'config.example.yaml').read_text())
if not c['storage']['automatic_drive_sync']:
    print('Automatic Drive sync disabled: separate offline OAuth not connected')
    sys.exit(0)
pointer=root/'.runtime/archive/latest_validated.json'
if not pointer.exists(): raise RuntimeError('No validated archive to upload')
latest=json.loads(pointer.read_text())
archive=pointer.parent/latest['path']
subprocess.run([sys.executable,str(root/'cloud/drive_sync.py'),str(archive),'--folder-id',c['storage']['drive_folder_id']],check=True)
