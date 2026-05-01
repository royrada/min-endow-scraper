import ast

class ScraperConfig:
    def __init__(self, params_dict):
        for key, value in params_dict.items():
            setattr(self, key, value)

def load_parameters_txt(path='inputs/parameters.txt'):
    params = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip()
            # Safely evaluate set/dict/list/number
            try:
                params[key] = ast.literal_eval(val)
            except Exception:
                params[key] = val
    return ScraperConfig(params)
