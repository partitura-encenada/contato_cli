from pathlib import Path

# Agenda ID -> porta COM é local de cada PC (fora do git); cria vazia se faltar
_com_contato_dict_file = Path(__file__).parent / 'com_contato_dict.py'
if not _com_contato_dict_file.exists():
    _com_contato_dict_file.write_text('com_contato_dict = {}\n', encoding='utf-8')
